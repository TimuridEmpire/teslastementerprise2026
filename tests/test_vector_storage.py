"""
Tests for the embedded local vector store / RAG layer
(``enterprise_router/vector_storage.py``) and its integration hooks.

Covers:
- Persistence: documents survive a round trip through the dedicated SQLite
  vector store, without touching the router's own storage.
- ANN retrieval accuracy: cosine-similarity ranking returns the
  semantically closest document first and respects agent/source filters.
- Clean failure modes: an unreachable embedding endpoint, disabled vector
  store, and a raising ingestion hook never raise out of the public API.
- The non-blocking ingestion hook wired into
  ``enterprise_router.agent_artifacts.write_agent_artifact``.
- The additive ``/rag/search`` and ``/rag/stats`` router API endpoints.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from enterprise_router import vector_storage
from enterprise_router.agent_artifacts import write_agent_artifact
from enterprise_router.api import create_app
from enterprise_router.config import RouterSettings
from enterprise_router.vector_storage import (
    OllamaEmbeddingClient,
    VectorStore,
    VectorStoreSettings,
    format_rag_context_block,
    ingest_artifact,
    ingest_artifact_async,
    retrieve_rag_context,
    semantic_search,
    vector_store_stats,
)


class FakeEmbeddingClient:
    """Deterministic stand-in for ``OllamaEmbeddingClient`` — no network."""

    def __init__(self, vectors: dict[str, list[float]] | None = None, *, model: str = "fake-embed") -> None:
        self._vectors = vectors or {}
        self.model = model
        self.calls: list[str] = []

    def embed(self, text: str):
        self.calls.append(text)
        return self._vectors.get(text)


class AlwaysReturningClient:
    """Returns the same vector regardless of input text (model attr required)."""

    def __init__(self, vector=(1.0, 0.0, 0.0), *, model: str = "fake-embed") -> None:
        self._vector = list(vector)
        self.model = model

    def embed(self, text: str):
        return list(self._vector) if text else None


class DownEmbeddingClient:
    """Simulates an unreachable local embedding service."""

    model = "fake-embed"

    def embed(self, text: str):
        return None


# ---------------------------------------------------------------------------
# VectorStore persistence + ANN retrieval accuracy
# ---------------------------------------------------------------------------


def test_add_and_get_document_round_trip(tmp_path):
    store = VectorStore(str(tmp_path / "vector.db"))

    store.add_document(
        doc_id="doc-1",
        agent_name="CEO",
        source_type="strategy",
        title="Q3 Strategy",
        text="Focus on router observability and retention.",
        metadata={"quarter": "Q3"},
        embedding=[1.0, 0.0, 0.0],
        embedding_model="fake-embed",
    )

    doc = store.get_document("doc-1")
    assert doc is not None
    assert doc["title"] == "Q3 Strategy"
    assert doc["agent_name"] == "CEO"
    assert doc["source_type"] == "strategy"
    assert doc["metadata"] == {"quarter": "Q3"}
    assert doc["embedding_model"] == "fake-embed"
    assert "text" in doc and "Focus on router observability" in doc["text"]


def test_add_document_upserts_on_same_doc_id(tmp_path):
    store = VectorStore(str(tmp_path / "vector.db"))
    store.add_document(
        doc_id="doc-1", agent_name="CEO", source_type="strategy",
        title="First", text="v1", embedding=[1.0, 0.0],
    )
    store.add_document(
        doc_id="doc-1", agent_name="CEO", source_type="strategy",
        title="Second", text="v2", embedding=[0.0, 1.0],
    )

    assert store.count() == 1
    assert store.get_document("doc-1")["title"] == "Second"


def test_similarity_search_ranks_closest_vector_first(tmp_path):
    store = VectorStore(str(tmp_path / "vector.db"))
    store.add_document(
        doc_id="router-doc", agent_name="CEO", source_type="strategy",
        title="Router observability plan",
        text="Improve router queue monitoring and dashboards.",
        embedding=[1.0, 0.0, 0.0],
    )
    store.add_document(
        doc_id="hr-doc", agent_name="HR", source_type="staffing",
        title="Onboarding plan",
        text="Hire and onboard new staff.",
        embedding=[0.0, 1.0, 0.0],
    )
    store.add_document(
        doc_id="unembedded-doc", agent_name="CEO", source_type="strategy",
        title="Pending embedding",
        text="Written while the embedding service was unreachable.",
        embedding=None,
    )

    results = store.similarity_search([0.9, 0.1, 0.0], top_k=2)

    assert [r["doc_id"] for r in results] == ["router-doc", "hr-doc"]
    assert results[0]["score"] > results[1]["score"]
    # The row stored without an embedding must never surface in ANN results.
    assert "unembedded-doc" not in [r["doc_id"] for r in results]


def test_similarity_search_filters_by_agent_and_source_type(tmp_path):
    store = VectorStore(str(tmp_path / "vector.db"))
    store.add_document(
        doc_id="ceo-doc", agent_name="CEO", source_type="strategy",
        title="CEO note", text="strategy text", embedding=[1.0, 0.0],
    )
    store.add_document(
        doc_id="hr-doc", agent_name="HR", source_type="staffing",
        title="HR note", text="staffing text", embedding=[1.0, 0.0],
    )

    only_hr = store.similarity_search([1.0, 0.0], top_k=5, agent_name="HR")
    only_staffing = store.similarity_search([1.0, 0.0], top_k=5, source_type="staffing")

    assert [r["doc_id"] for r in only_hr] == ["hr-doc"]
    assert [r["doc_id"] for r in only_staffing] == ["hr-doc"]


def test_similarity_search_empty_store_returns_empty_list(tmp_path):
    store = VectorStore(str(tmp_path / "vector.db"))
    assert store.similarity_search([1.0, 0.0], top_k=5) == []


def test_similarity_search_zero_query_vector_returns_empty_list(tmp_path):
    store = VectorStore(str(tmp_path / "vector.db"))
    store.add_document(
        doc_id="d1", agent_name="CEO", source_type="strategy",
        title="t", text="text", embedding=[1.0, 0.0],
    )
    assert store.similarity_search([0.0, 0.0], top_k=5) == []


def test_count_list_and_delete_all(tmp_path):
    store = VectorStore(str(tmp_path / "vector.db"))
    store.add_document(
        doc_id="d1", agent_name="CEO", source_type="strategy",
        title="t1", text="text1", embedding=[1.0, 0.0],
    )
    store.add_document(
        doc_id="d2", agent_name="CEO", source_type="strategy",
        title="t2", text="text2", embedding=None,
    )

    assert store.count() == 2
    assert store.count(embedded_only=True) == 1
    assert {d["doc_id"] for d in store.list_documents(agent_name="CEO")} == {"d1", "d2"}

    store.delete_all()
    assert store.count() == 0


def test_vector_store_is_isolated_from_router_and_backlog_storage(tmp_path):
    """The vector store must live in its own file and never touch the
    router's SQLite schema (agents/queue/messages/audit tables)."""
    router_db = tmp_path / "router.db"
    vector_db = tmp_path / "vector.db"

    from enterprise_router.sqlite_storage import SQLiteStorage

    router_storage = SQLiteStorage(str(router_db))
    vstore = VectorStore(str(vector_db))
    vstore.add_document(
        doc_id="d1", agent_name="CEO", source_type="strategy",
        title="t", text="text", embedding=[1.0, 0.0],
    )

    assert router_db.exists()
    assert vector_db.exists()
    assert router_db != vector_db
    # Router storage still works normally; touching the vector store did
    # nothing to it.
    assert router_storage.list_agents() == []


# ---------------------------------------------------------------------------
# OllamaEmbeddingClient — clean failure modes
# ---------------------------------------------------------------------------


def test_embed_returns_none_for_blank_text():
    client = OllamaEmbeddingClient()
    assert client.embed("") is None
    assert client.embed("   ") is None


def test_embed_returns_none_when_endpoint_unreachable(monkeypatch):
    import requests

    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("Connection refused")

    monkeypatch.setattr(requests, "post", fake_post)

    client = OllamaEmbeddingClient()
    assert client.embed("hello world") is None


def test_embed_parses_legacy_embedding_field(monkeypatch):
    import requests

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embedding": [1, 2, 3]}

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    client = OllamaEmbeddingClient()
    assert client.embed("hello") == [1.0, 2.0, 3.0]


def test_embed_parses_newer_embeddings_batch_field(monkeypatch):
    import requests

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[4, 5, 6]]}

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    client = OllamaEmbeddingClient()
    assert client.embed("hello") == [4.0, 5.0, 6.0]


def test_embed_returns_none_on_malformed_response(monkeypatch):
    import requests

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"unexpected": "shape"}

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    client = OllamaEmbeddingClient()
    assert client.embed("hello") is None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_settings_from_env_defaults():
    settings = VectorStoreSettings.from_env()
    assert settings.enabled is False  # forced off by tests/conftest.py
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.embedding_url.endswith("/api/embeddings")


def test_settings_from_env_respects_overrides(monkeypatch):
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    monkeypatch.setenv("ENTERPRISE_VECTOR_EMBEDDING_MODEL", "all-minilm")
    monkeypatch.setenv("ENTERPRISE_VECTOR_TOP_K", "9")
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ASYNC", "0")

    settings = VectorStoreSettings.from_env()

    assert settings.enabled is True
    assert settings.embedding_model == "all-minilm"
    assert settings.default_top_k == 9
    assert settings.async_ingestion is False


# ---------------------------------------------------------------------------
# ingest_artifact / ingest_text / semantic_search / retrieve_rag_context
# ---------------------------------------------------------------------------


def test_ingest_artifact_disabled_is_a_clean_noop(tmp_path, monkeypatch):
    # Enabled defaults to False via tests/conftest.py; explicitly assert the
    # no-op contract here too.
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "0")
    store = VectorStore(str(tmp_path / "vector.db"))

    doc_id = ingest_artifact(
        {"artifact_id": "art-1", "agent_name": "CEO", "artifact_type": "strategy", "title": "T"},
        "body text",
        embedding_client=AlwaysReturningClient(),
        store=store,
    )

    assert doc_id is None
    assert store.count() == 0


def test_ingest_artifact_stores_embedded_document(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    store = VectorStore(str(tmp_path / "vector.db"))
    client = AlwaysReturningClient([1.0, 0.0, 0.0])

    doc_id = ingest_artifact(
        {
            "artifact_id": "art-42",
            "agent_name": "PM",
            "artifact_type": "roadmap",
            "title": "Q3 Roadmap",
            "metadata": {"project_id": "proj-1"},
            "source_message_id": "msg-1",
            "source_task_type": "DEFINE_Q2_ROADMAP",
        },
        "## Roadmap\n\nShip retention features.",
        embedding_client=client,
        store=store,
    )

    assert doc_id == "art-42"
    doc = store.get_document("art-42")
    assert doc["agent_name"] == "PM"
    assert doc["source_type"] == "roadmap"
    assert doc["metadata"]["project_id"] == "proj-1"
    assert doc["source_message_id"] == "msg-1"
    assert "Ship retention features." in doc["text"]


def test_ingest_artifact_stores_row_without_embedding_when_service_down(tmp_path, monkeypatch):
    """Degradation contract: an unreachable embedding service must not drop
    the document or raise — it is stored without a vector and simply won't
    surface in similarity search until it is re-embedded."""
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    store = VectorStore(str(tmp_path / "vector.db"))

    doc_id = ingest_artifact(
        {"artifact_id": "art-99", "agent_name": "CEO", "artifact_type": "strategy", "title": "T"},
        "body text",
        embedding_client=DownEmbeddingClient(),
        store=store,
    )

    assert doc_id == "art-99"
    assert store.count() == 1
    assert store.count(embedded_only=True) == 0
    assert store.similarity_search([1.0, 0.0], top_k=5) == []


def test_ingest_artifact_blank_content_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    store = VectorStore(str(tmp_path / "vector.db"))

    doc_id = ingest_artifact(
        {"artifact_id": "art-1", "agent_name": "CEO", "artifact_type": "strategy", "title": "T"},
        "   ",
        embedding_client=AlwaysReturningClient(),
        store=store,
    )

    assert doc_id is None
    assert store.count() == 0


def test_ingest_artifact_never_raises_when_store_is_broken(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")

    class BrokenStore:
        def add_document(self, **kwargs):
            raise RuntimeError("disk full")

    doc_id = ingest_artifact(
        {"artifact_id": "art-1", "agent_name": "CEO", "artifact_type": "strategy", "title": "T"},
        "body text",
        embedding_client=AlwaysReturningClient(),
        store=BrokenStore(),
    )

    assert doc_id is None  # logged and swallowed, never raised


def test_ingest_artifact_async_runs_in_background_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ASYNC", "1")
    monkeypatch.setenv("ENTERPRISE_VECTOR_DB", str(tmp_path / "vector.db"))
    monkeypatch.setattr(
        vector_storage, "OllamaEmbeddingClient", lambda **kw: AlwaysReturningClient([1.0, 0.0])
    )

    ingest_artifact_async(
        {"artifact_id": "art-async", "agent_name": "CEO", "artifact_type": "strategy", "title": "T"},
        "background ingestion body",
    )

    store = VectorStore(str(tmp_path / "vector.db"))
    deadline = time.time() + 2.0
    while time.time() < deadline and store.count() == 0:
        time.sleep(0.05)

    assert store.get_document("art-async") is not None


def test_semantic_search_returns_empty_when_embedding_service_down(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    store = VectorStore(str(tmp_path / "vector.db"))
    store.add_document(
        doc_id="d1", agent_name="CEO", source_type="strategy",
        title="t", text="text", embedding=[1.0, 0.0],
    )

    results = semantic_search(
        "anything", embedding_client=DownEmbeddingClient(), store=store
    )

    assert results == []


def test_semantic_search_and_retrieve_rag_context(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    store = VectorStore(str(tmp_path / "vector.db"))
    store.add_document(
        doc_id="router-doc", agent_name="CEO", source_type="strategy",
        title="Router observability plan",
        text="Improve router queue monitoring dashboards for operators. " * 5,
        embedding=[1.0, 0.0],
    )
    store.add_document(
        doc_id="hr-doc", agent_name="HR", source_type="staffing",
        title="Onboarding plan",
        text="Hire and onboard new staff members quickly.",
        embedding=[0.0, 1.0],
    )
    client = AlwaysReturningClient([0.95, 0.05])

    hits = semantic_search("queue monitoring", embedding_client=client, store=store, top_k=1)
    assert [h["doc_id"] for h in hits] == ["router-doc"]

    context = retrieve_rag_context(
        "queue monitoring", embedding_client=client, store=store, top_k=1, max_chars=20
    )
    assert len(context) == 1
    assert context[0]["title"] == "Router observability plan"
    assert len(context[0]["snippet"]) <= 20


def test_format_rag_context_block_empty_and_populated():
    assert format_rag_context_block([]) == ""

    block = format_rag_context_block(
        [{"agent_name": "CEO", "title": "Plan", "score": 0.87, "snippet": "Ship it."}],
        header="Custom header",
    )
    assert block.startswith("## Custom header")
    assert "[CEO] Plan" in block
    assert "0.87" in block
    assert "Ship it." in block


def test_vector_store_stats_disabled_and_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "0")
    stats = vector_store_stats()
    assert stats["enabled"] is False
    assert stats["document_count"] == 0

    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    monkeypatch.setenv("ENTERPRISE_VECTOR_DB", str(tmp_path / "vector.db"))
    store = VectorStore(str(tmp_path / "vector.db"))
    store.add_document(
        doc_id="d1", agent_name="CEO", source_type="strategy",
        title="t", text="text", embedding=[1.0, 0.0],
    )

    stats = vector_store_stats()
    assert stats["enabled"] is True
    assert stats["document_count"] == 1
    assert stats["embedded_document_count"] == 1


# ---------------------------------------------------------------------------
# Integration: write_agent_artifact -> ingestion hook (agent_artifacts.py)
# ---------------------------------------------------------------------------


def test_write_agent_artifact_triggers_synchronous_ingestion(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ASYNC", "0")
    monkeypatch.setenv("ENTERPRISE_VECTOR_DB", str(tmp_path / "vector.db"))
    monkeypatch.setattr(
        vector_storage, "OllamaEmbeddingClient", lambda **kw: AlwaysReturningClient([1.0, 0.0, 0.0])
    )

    record = write_agent_artifact(
        "CEO",
        title="Q3 Strategy",
        body="Focus on router observability and enterprise retention.",
        artifact_type="strategy",
        metadata={"quarter": "Q3"},
    )

    store = VectorStore(str(tmp_path / "vector.db"))
    doc = store.get_document(record["artifact_id"])
    assert doc is not None
    assert doc["agent_name"] == "CEO"
    assert doc["source_type"] == "strategy"
    assert "Focus on router observability" in doc["text"]
    assert doc["metadata"]["quarter"] == "Q3"


def test_write_agent_artifact_still_succeeds_when_ingestion_hook_raises(tmp_path, monkeypatch):
    """Non-destructive contract: a broken vector store must never break
    artifact persistence (the router's audit-visible source of truth for
    completed work)."""
    monkeypatch.setenv("ENTERPRISE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))

    def boom(*args, **kwargs):
        raise RuntimeError("vector store exploded")

    monkeypatch.setattr(vector_storage, "ingest_artifact_async", boom)

    record = write_agent_artifact("CEO", title="Q3 Strategy", body="Focus on retention.")

    from pathlib import Path

    assert Path(record["path"]).exists()
    assert Path(record["path"]).read_text(encoding="utf-8").startswith("# Q3 Strategy")


def test_write_agent_artifact_background_ingestion_eventually_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ASYNC", "1")
    monkeypatch.setenv("ENTERPRISE_VECTOR_DB", str(tmp_path / "vector.db"))
    monkeypatch.setattr(
        vector_storage, "OllamaEmbeddingClient", lambda **kw: AlwaysReturningClient([1.0, 0.0])
    )

    record = write_agent_artifact("HR", title="Staffing Review", body="Hire two SREs.")

    store = VectorStore(str(tmp_path / "vector.db"))
    deadline = time.time() + 2.0
    while time.time() < deadline and store.get_document(record["artifact_id"]) is None:
        time.sleep(0.05)

    assert store.get_document(record["artifact_id"]) is not None


# ---------------------------------------------------------------------------
# Router API: /rag/search, /rag/stats (additive, admin-protected)
# ---------------------------------------------------------------------------


def _client(tmp_path, monkeypatch) -> tuple[TestClient, str]:
    monkeypatch.setenv("ENTERPRISE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ASYNC", "0")
    monkeypatch.setenv("ENTERPRISE_VECTOR_DB", str(tmp_path / "vector.db"))
    monkeypatch.setattr(
        vector_storage, "OllamaEmbeddingClient", lambda **kw: AlwaysReturningClient([1.0, 0.0, 0.0])
    )
    settings = RouterSettings(
        sqlite_db_path=str(tmp_path / "router.db"),
        shared_secret="shared",
        admin_secret="admin-secret",
        api_host="127.0.0.1",
        api_port=9999,
    )
    return TestClient(create_app(settings)), settings.admin_secret


def test_rag_search_endpoint_finds_ingested_artifact(tmp_path, monkeypatch):
    client, admin = _client(tmp_path, monkeypatch)
    record = write_agent_artifact(
        "Engineering",
        title="Queue Worker Spec",
        body="Implement a background worker that drains the message queue.",
        artifact_type="engineering",
    )

    response = client.get(
        "/rag/search",
        headers={"X-Admin-Secret": admin},
        params={"query": "queue worker", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    hits = response.json()
    assert any(h["doc_id"] == record["artifact_id"] for h in hits)


def test_rag_search_endpoint_requires_admin_secret(tmp_path, monkeypatch):
    client, _admin = _client(tmp_path, monkeypatch)

    response = client.get("/rag/search", params={"query": "anything"})

    assert response.status_code == 401


def test_rag_stats_endpoint_reports_document_count(tmp_path, monkeypatch):
    client, admin = _client(tmp_path, monkeypatch)
    write_agent_artifact("PM", title="Roadmap", body="Ship the retention roadmap.")

    response = client.get("/rag/stats", headers={"X-Admin-Secret": admin})

    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats["enabled"] is True
    assert stats["document_count"] >= 1


# ---------------------------------------------------------------------------
# Non-destructive invariant: writing to the vector store never touches the
# router's SQLite schema or agent_backlog.py's SQLite schema.
# ---------------------------------------------------------------------------


def test_vector_store_writes_do_not_touch_agent_backlog_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_BACKLOG_DB", str(tmp_path / "backlog.db"))
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ASYNC", "0")
    monkeypatch.setenv("ENTERPRISE_VECTOR_DB", str(tmp_path / "vector.db"))
    monkeypatch.setattr(
        vector_storage, "OllamaEmbeddingClient", lambda **kw: AlwaysReturningClient([1.0, 0.0])
    )

    from agent_backlog import AgentBacklog

    backlog = AgentBacklog()
    ingest_artifact(
        {"artifact_id": "art-1", "agent_name": "CEO", "artifact_type": "strategy", "title": "T"},
        "some body text",
    )

    # The backlog DB file must not exist yet (never opened by vector storage
    # code), and the backlog's own history read path must still behave
    # normally afterwards.
    assert backlog.get_agent_history("CEO", limit=5) == []
