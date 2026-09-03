"""Ingest the reference corpus (uploads/*.md) into the knowledge store.

Only documents that exist are ingested — never pretend-ingested files (D-014
discipline). Idempotent: re-running is a no-op for unchanged content.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.knowledge.rag import ingest_document  # noqa: E402
from db.engine import apply_migrations, make_engine, make_sessionmaker  # noqa: E402
UPLOADS = Path(__file__).resolve().parents[1]

# kind classification for the 12 known docs (fallback: "doc")
KIND = {
    "IMPLEMENTATION_PROMPT": "spec",
    "PHASE_1": "research",
    "PHASE_2": "strategy",
    "PHASE_3A": "blueprint",
    "PHASE_3B": "plan",
    "PHASE_3C": "ml-contract",
    "DATASET_BUILD_REPORT": "report",
    "MODEL_QUALITY_EVALUATOR_DEFENSE": "evaluation",
}


def classify(name: str) -> str:
    for key, kind in KIND.items():
        if name.startswith(key):
            return kind
    return "doc"


def main() -> int:
    apply_migrations()
    sm = make_sessionmaker(make_engine())
    docs = sorted(UPLOADS.glob("*.md"))
    if not docs:
        print("no reference documents found — knowledge store stays empty (truthful)")
        return 0
    results = []
    with sm.begin() as s:
        for doc in docs:
            kind = classify(doc.name)
            res = ingest_document(s, title=doc.name, kind=kind,
                                  content=doc.read_text(encoding="utf-8"),
                                  uri=f"file://{doc}")
            results.append(res)
            print(f"  {res['status']:10s} {res['chunks']:4d} chunks  {doc.name}")
        # index after data exists
        s.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_kchunks_embedding "
            "ON knowledge.chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 4)"
        )) if sum(r["chunks"] for r in results) > 0 else None
    print(f"knowledge store: {len(docs)} sources, "
          f"{sum(r['chunks'] for r in results)} chunks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
