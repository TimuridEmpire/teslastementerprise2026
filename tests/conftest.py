"""Shared pytest fixtures.

``enterprise_router/agent_artifacts.py`` now fires a best-effort semantic
indexing hook (see ``enterprise_router/vector_storage.py``) on every
``write_agent_artifact(...)`` call, and ``ceo_agent.py`` / ``pm_agent.py`` /
``engineering_agent.py`` call RAG retrieval helpers that talk to a local
Ollama embedding endpoint. Both are designed to degrade to a fast no-op when
disabled or unreachable.

Disable the vector store by default across the whole suite so:

- Existing tests that don't know about RAG never make a real network call
  to ``http://localhost:11434`` (avoids flakiness/slowness on machines that
  do have a local Ollama running) and never write to the repository's real
  ``vector_store.db`` as a side effect.
- Tests that exercise the vector store explicitly re-enable it
  (``monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "1")``) and point
  ``ENTERPRISE_VECTOR_DB`` at their own ``tmp_path``.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_vector_store(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_VECTOR_STORE_ENABLED", "0")
    monkeypatch.setenv("ENTERPRISE_VECTOR_DB", str(tmp_path / "vector_store.db"))
    yield
