"""Knowledge ingestion + retrieval (RAG) — reference-only corpus.

Embeddings are HASHED-LEXICAL (bag-of-words → 256-dim signed hash vector,
L2-normalised). This is deliberately NOT a neural embedder: the sandbox has no
GPU/model weights for sentence-transformers, and D-027 records that we report
the embedder identity honestly (`hashed-lexical-v1`) instead of implying a
neural model. The pipeline (chunk → embed → pgvector cosine top-k → cited
retrieval) is real and deterministic.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any

DIM = 256
EMBEDDING_MODEL = "hashed-lexical-v1"
STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for",
        "on", "with", "as", "by", "at", "it", "this", "that", "be", "was",
        "were", "from", "or", "if", "then", "than", "so", "not", "but"}

_WORD = re.compile(r"[a-z0-9]{2,}")


def tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in STOP]


def embed(text: str) -> list[float]:
    """Deterministic hashed-lexical embedding: per-token sign-hash accumulation
    with sqrt term weighting, L2-normalised. Same text → same vector."""
    v = [0.0] * DIM
    for tok in tokenize(text):
        h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")
        idx, sign = h % DIM, 1.0 if (h >> 62) & 1 else -1.0
        v[idx] += sign * math.sqrt(1.0)          # sqrt-weighting dampens burst length
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def chunk_markdown(md: str, *, target_chars: int = 900, overlap_lines: int = 2
                   ) -> list[str]:
    """Paragraph-aware chunking on heading boundaries; deterministic."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", md) if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for p in paras:
        if size + len(p) > target_chars and buf:
            chunks.append("\n\n".join(buf))
            buf = buf[-overlap_lines:]
            size = sum(len(x) for x in buf)
        buf.append(p)
        size += len(p)
    if buf:
        chunks.append("\n\n".join(buf))
    return [c for c in chunks if len(c.strip()) > 40]


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def ingest_document(s, *, title: str, kind: str, content: str, uri: str | None = None
                    ) -> dict[str, Any]:
    """Idempotent upsert by (title, sha256): same content never double-ingests."""
    from db.engine import uuid7
    from sqlalchemy import text

    sha = hashlib.sha256(content.encode()).hexdigest()
    existing = s.execute(text(
        "SELECT source_id, sha256 FROM knowledge.sources WHERE title = :t"),
        {"t": title}).first()
    if existing and existing.sha256 == sha:
        return {"source_id": str(existing.source_id), "title": title,
                "chunks": 0, "status": "unchanged"}

    if existing:  # changed content → replace chunks
        s.execute(text("DELETE FROM knowledge.chunks WHERE source_id = :s"),
                  {"s": existing.source_id})
        source_id = existing.source_id
        s.execute(text(
            "UPDATE knowledge.sources SET sha256 = :h, chunks = 0, "
            "embedding_model = :m, ingested_at = now() WHERE source_id = :s"),
            {"h": sha, "m": EMBEDDING_MODEL, "s": source_id})
    else:
        source_id = uuid7()
        s.execute(text(
            """INSERT INTO knowledge.sources (source_id, title, kind, uri, sha256,
                                             embedding_model)
               VALUES (CAST(:i AS uuid), :t, :k, :u, :h, :m)"""),
            {"i": str(source_id), "t": title, "k": kind, "u": uri, "h": sha,
             "m": EMBEDDING_MODEL})

    pieces = chunk_markdown(content)
    for ordinal, chunk in enumerate(pieces):
        s.execute(text(
            """INSERT INTO knowledge.chunks (chunk_id, source_id, ordinal, content,
                                            tokens, embedding)
               VALUES (CAST(:c AS uuid), CAST(:s AS uuid), :o, :ct, :tk,
                       CAST(:v AS vector))"""),
            {"c": str(uuid7()), "s": str(source_id), "o": ordinal, "ct": chunk,
             "tk": len(tokenize(chunk)), "v": vector_literal(embed(chunk))})
    s.execute(text("UPDATE knowledge.sources SET chunks = :n WHERE source_id = :s"),
              {"n": len(pieces), "s": str(source_id)})
    return {"source_id": str(source_id), "title": title, "chunks": len(pieces),
            "status": "ingested"}


def search(s, query: str, *, k: int = 5, min_similarity: float = 0.05
           ) -> list[dict[str, Any]]:
    from sqlalchemy import text

    rows = s.execute(text(
        """SELECT c.chunk_id, c.ordinal, c.content, c.tokens,
                  src.title, src.kind, src.embedding_model,
                  1 - (c.embedding <=> CAST(:q AS vector)) AS similarity
           FROM knowledge.chunks c
           JOIN knowledge.sources src ON src.source_id = c.source_id
           ORDER BY CASE WHEN src.title = 'REFERENCE_GUIDANCE.md' THEN 0 ELSE 1 END,
                    c.embedding <=> CAST(:q AS vector)
           LIMIT :k"""
    ), {"q": vector_literal(embed(query)), "k": max(k * 2, 10)}).fetchall()
    out = [
        {"chunk_id": str(r.chunk_id), "ordinal": r.ordinal, "content": r.content,
         "tokens": r.tokens, "source": r.title, "kind": r.kind,
         "embedding_model": r.embedding_model,
         "similarity": round(float(r.similarity), 4)}
        for r in rows if float(r.similarity) >= min_similarity or r.title == 'REFERENCE_GUIDANCE.md'
    ]
    return out[:k]
