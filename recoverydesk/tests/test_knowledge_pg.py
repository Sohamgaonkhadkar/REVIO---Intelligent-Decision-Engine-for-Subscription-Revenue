"""Knowledge/RAG + deterministic-explain API tests (live PG)."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from apps.api.main import app
from db.engine import make_engine, make_sessionmaker

pytestmark = pytest.mark.order(-3)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def sm():
    eng = make_engine()
    yield make_sessionmaker(eng)
    eng.dispose()


# ---------------------------------------------------------------- RAG
def test_knowledge_corpus_real(client):
    body = client.get("/api/knowledge").json()
    assert body["rag_enabled"] is True
    assert body["stats"]["chunks"] >= 500          # 762 from the 12 real docs
    assert len(body["sources"]) == 12
    assert body["embedding_model"] == "hashed-lexical-v1"   # honest identity


def test_rag_search_cites_sources(client):
    body = client.get("/api/knowledge/search",
                      params={"q": "quiet hours retry window"}).json()
    assert body["query"] == "quiet hours retry window"
    assert len(body["results"]) >= 1
    for r in body["results"]:
        assert r["source"].endswith(".md")
        assert 0.0 <= r["similarity"] <= 1.0
        assert len(r["content"]) > 40


def test_rag_retrieval_is_deterministic(client):
    a = client.get("/api/knowledge/search", params={"q": "mandate paused"}).json()
    b = client.get("/api/knowledge/search", params={"q": "mandate paused"}).json()
    assert [r["chunk_id"] for r in a["results"]] == [r["chunk_id"] for r in b["results"]]
    assert [r["similarity"] for r in a["results"]] == [r["similarity"] for r in b["results"]]


def test_rag_relevant_doc_wins(client):
    """A query about EV economics must retrieve the decision/EV docs first."""
    body = client.get("/api/knowledge/search",
                      params={"q": "expected value shadow price retry"}).json()
    top_sources = " ".join(r["source"] for r in body["results"][:3])
    assert any(k in top_sources for k in
               ("PHASE_1", "PHASE_4", "IMPLEMENTATION_PROMPT", "PHASE_2")), top_sources


def test_rag_validation(client):
    assert client.get("/api/knowledge/search", params={"q": "x"}).status_code == 422


# ---------------------------------------------------------------- explain
def test_explain_endpoint_deterministic(client, sm):
    with sm.begin() as s:
        row = s.execute(text(
            "SELECT case_id, decision_id FROM decision_records ORDER BY taken_at DESC LIMIT 1"
        )).first()
    r1 = client.get(f"/api/cases/{row.case_id}/decisions/{row.decision_id}/explain")
    r2 = client.get(f"/api/cases/{row.case_id}/decisions/{row.decision_id}/explain")
    assert r1.status_code == 200
    body = r1.json()
    assert body["decision_seq"] >= 1
    steps = [s["step"] for s in body["steps"]]
    assert steps[:3] == ["trigger", "policy", "evidence-integrity"]
    assert "selection" in steps
    joined = " ".join(s["detail"] for s in body["steps"])
    assert "constants_hash=" in joined and "rule_pack=" in joined
    # byte-stable: same decision -> identical payload
    import json as _json
    assert _json.dumps(body, sort_keys=True) == _json.dumps(r2.json(), sort_keys=True)


def test_explain_404s(client):
    fake = str(uuid.uuid4())
    cid = client.get("/api/cases?limit=1").json()["items"][0]["case_id"]
    assert client.get(f"/api/cases/{cid}/decisions/{fake}/explain").status_code == 404
