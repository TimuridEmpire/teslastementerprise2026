"""
enterprise_router/vector_storage.py

Embedded, local vector storage layer for semantic conceptual search and
local Retrieval-Augmented Generation (RAG) across agent artifacts, code
snippets, and planning documents.

Design constraints (see README "Storage Backends" and the router-centered
architecture described throughout this repo):

- **Non-destructive / additive only.** This module owns its own SQLite
  database (default: ``<repo>/vector_store.db``, override with
  ``ENTERPRISE_VECTOR_DB``). It never opens, reads, or writes
  ``enterprise_router.db`` / ``enterprise_backlog.db`` / ``pm_storage.json``
  or any table owned by ``enterprise_router/sqlite_storage.py``,
  ``enterprise_router/router_storage.py``, or ``agent_backlog.py``. Nothing
  in the router's queue/lease/audit pipeline depends on this module being
  importable, healthy, or even installed.
- **Local, embedded, zero cloud dependencies.** Persistence is plain SQLite
  on disk. Approximate nearest neighbor search is brute-force cosine
  similarity over stored embedding vectors using numpy — no external
  vector database service, and no network calls other than the local
  embedding endpoint below.
- **Local embeddings only.** Embeddings are produced by a local
  Ollama-compatible HTTP endpoint (``http://localhost:11434/api/embeddings``
  by default), consistent with the existing CEO (``ceo_agent.py``) and
  Engineering (``engineering_agent.py``) conventions of talking to a local
  Ollama instance.
- **Clean failure modes.** Every public entry point degrades gracefully: if
  SQLite, numpy, or the local embedding service is unavailable, functions
  log a warning and return an empty/``[]``/``None`` result rather than
  raising, so router queue polling and message ack/nack is never
  interrupted by a RAG failure.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

JsonDict = dict[str, Any]

logger = logging.getLogger("enterprise_router.vector_storage")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _truthy_env(value: str, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VectorStoreSettings:
    """Environment-driven configuration for the local vector store."""

    enabled: bool = True
    db_path: str = ""
    embedding_url: str = "http://localhost:11434/api/embeddings"
    embedding_model: str = "nomic-embed-text"
    embedding_timeout_s: float = 8.0
    default_top_k: int = 5
    async_ingestion: bool = True

    @classmethod
    def from_env(cls) -> "VectorStoreSettings":
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_db = os.path.join(repo_root, "vector_store.db")
        return cls(
            enabled=_truthy_env(os.getenv("ENTERPRISE_VECTOR_STORE_ENABLED", ""), default=True),
            db_path=os.getenv("ENTERPRISE_VECTOR_DB", default_db),
            embedding_url=os.getenv(
                "ENTERPRISE_VECTOR_EMBEDDING_URL", "http://localhost:11434/api/embeddings"
            ),
            embedding_model=os.getenv("ENTERPRISE_VECTOR_EMBEDDING_MODEL", "nomic-embed-text"),
            embedding_timeout_s=float(os.getenv("ENTERPRISE_VECTOR_EMBEDDING_TIMEOUT_S", "8")),
            default_top_k=int(os.getenv("ENTERPRISE_VECTOR_TOP_K", "5")),
            async_ingestion=_truthy_env(
                os.getenv("ENTERPRISE_VECTOR_STORE_ASYNC", ""), default=True
            ),
        )


def get_settings() -> VectorStoreSettings:
    """Read settings fresh from the environment (never cached, so tests /
    per-process overrides via ``monkeypatch.setenv`` take effect immediately,
    matching the pattern used by ``enterprise_paths.py``)."""
    return VectorStoreSettings.from_env()


# ---------------------------------------------------------------------------
# Local embedding client (Ollama-compatible)
# ---------------------------------------------------------------------------


class EmbeddingUnavailableError(Exception):
    """Raised internally when an embedding cannot be produced. Never leaks
    past this module's public functions — callers always get ``None``/``[]``
    instead so RAG failures cannot interrupt router message processing."""


class OllamaEmbeddingClient:
    """Thin HTTP client for a local Ollama-compatible embeddings endpoint."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.embedding_url).strip()
        self.model = (model or settings.embedding_model).strip()
        self.timeout_s = float(timeout_s if timeout_s is not None else settings.embedding_timeout_s)

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)

    def embed(self, text: str) -> Optional[list[float]]:
        """Return a dense embedding vector for ``text``, or ``None`` on any
        failure (unreachable Ollama, bad response, missing dependency)."""
        cleaned = (text or "").strip()
        if not cleaned or not self.is_configured():
            return None

        try:
            import requests
        except ImportError:  # pragma: no cover - requests is a hard dependency in this repo
            logger.warning("Embedding skipped: 'requests' package is unavailable.")
            return None

        try:
            response = requests.post(
                self.base_url,
                json={"model": self.model, "prompt": cleaned},
                timeout=self.timeout_s,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.warning(
                "Local embedding endpoint unreachable (%s); continuing without RAG context: %s",
                self.base_url,
                exc,
            )
            return None
        except ValueError as exc:
            logger.warning("Embedding endpoint returned invalid JSON: %s", exc)
            return None

        vector = self._extract_vector(data)
        if vector is None:
            logger.warning(
                "Embedding response from %s did not contain a usable vector.", self.base_url
            )
            return None
        return vector

    @staticmethod
    def _extract_vector(data: Any) -> Optional[list[float]]:
        if not isinstance(data, dict):
            return None
        vector = data.get("embedding")
        if not (isinstance(vector, list) and vector):
            # Newer Ollama /api/embed shape: {"embeddings": [[...]]}
            batch = data.get("embeddings")
            if isinstance(batch, list) and batch and isinstance(batch[0], list):
                vector = batch[0]
        if not (isinstance(vector, list) and vector):
            return None
        try:
            return [float(x) for x in vector]
        except (TypeError, ValueError):
            return None


# ---------------------------------------------------------------------------
# Embedded local vector store (SQLite + numpy brute-force ANN)
# ---------------------------------------------------------------------------


class VectorStore:
    """
    Embedded local vector database.

    Persistence is a dedicated SQLite file, completely separate from the
    router's own storage (``enterprise_router/sqlite_storage.py``) and from
    ``agent_backlog.py``. Similarity search is brute-force cosine similarity
    over stored dense embedding vectors — an ANN approach appropriate for
    the document volumes this simulation produces, with no external vector
    database service required.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        directory = os.path.dirname(os.path.abspath(db_path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS vector_documents (
                    doc_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'document',
                    title TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    embedding_json TEXT,
                    embedding_dim INTEGER NOT NULL DEFAULT 0,
                    embedding_model TEXT NOT NULL DEFAULT '',
                    artifact_id TEXT,
                    source_message_id TEXT,
                    source_task_type TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_vector_documents_agent
                    ON vector_documents(agent_name);
                CREATE INDEX IF NOT EXISTS idx_vector_documents_source_type
                    ON vector_documents(source_type);
                """
            )

    def add_document(
        self,
        *,
        doc_id: str,
        agent_name: str,
        source_type: str,
        title: str,
        text: str,
        metadata: Optional[JsonDict] = None,
        embedding: Optional[list[float]] = None,
        embedding_model: str = "",
        artifact_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        source_task_type: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> str:
        """Insert or replace one document. ``embedding`` may be ``None`` when
        the local embedding service was unreachable at ingestion time — the
        row is still stored (for later backfill/audit) but is excluded from
        similarity search until it has a vector."""
        embedding_json = json.dumps([float(x) for x in embedding]) if embedding else None
        embedding_dim = len(embedding) if embedding else 0
        now = created_at or _utc_now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO vector_documents (
                    doc_id, agent_name, source_type, title, text, metadata_json,
                    embedding_json, embedding_dim, embedding_model, artifact_id,
                    source_message_id, source_task_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    agent_name = excluded.agent_name,
                    source_type = excluded.source_type,
                    title = excluded.title,
                    text = excluded.text,
                    metadata_json = excluded.metadata_json,
                    embedding_json = excluded.embedding_json,
                    embedding_dim = excluded.embedding_dim,
                    embedding_model = excluded.embedding_model,
                    artifact_id = excluded.artifact_id,
                    source_message_id = excluded.source_message_id,
                    source_task_type = excluded.source_task_type,
                    created_at = excluded.created_at
                """,
                (
                    doc_id,
                    agent_name,
                    source_type,
                    title,
                    text,
                    json.dumps(metadata or {}, default=str),
                    embedding_json,
                    embedding_dim,
                    embedding_model,
                    artifact_id,
                    source_message_id,
                    source_task_type,
                    now,
                ),
            )
        return doc_id

    def get_document(self, doc_id: str) -> Optional[JsonDict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM vector_documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        return self._public_row(row) if row is not None else None

    def count(self, *, embedded_only: bool = False) -> int:
        query = "SELECT COUNT(*) FROM vector_documents"
        if embedded_only:
            query += " WHERE embedding_json IS NOT NULL"
        with self._connect() as conn:
            (total,) = conn.execute(query).fetchone()
        return int(total)

    def list_documents(
        self, *, agent_name: Optional[str] = None, source_type: Optional[str] = None, limit: int = 50
    ) -> list[JsonDict]:
        rows = self._fetch_candidates(
            agent_name=agent_name, source_type=source_type, embedded_only=False
        )
        rows.sort(key=lambda r: str(r["created_at"] or ""), reverse=True)
        return [self._public_row(row) for row in rows[: max(0, limit)]]

    def delete_all(self) -> None:
        """Test/admin helper: clear the vector store without touching any
        other persistence backend."""
        with self._connect() as conn:
            conn.execute("DELETE FROM vector_documents")

    def similarity_search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        agent_name: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> list[JsonDict]:
        """Brute-force cosine-similarity ANN search over stored embeddings."""
        if not query_embedding:
            return []

        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy is a hard dependency in this repo
            logger.warning("Similarity search skipped: numpy is unavailable.")
            return []

        rows = self._fetch_candidates(
            agent_name=agent_name, source_type=source_type, embedded_only=True
        )
        if not rows:
            return []

        query_vec = np.asarray(query_embedding, dtype=np.float32)
        query_norm = float(np.linalg.norm(query_vec))
        if query_norm == 0.0:
            return []

        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            try:
                candidate = np.asarray(json.loads(row["embedding_json"]), dtype=np.float32)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if candidate.shape != query_vec.shape:
                continue
            candidate_norm = float(np.linalg.norm(candidate))
            if candidate_norm == 0.0:
                continue
            score = float(np.dot(query_vec, candidate) / (query_norm * candidate_norm))
            scored.append((score, row))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [self._public_row(row, score=score) for score, row in scored[: max(0, top_k)]]

    def _fetch_candidates(
        self,
        *,
        agent_name: Optional[str],
        source_type: Optional[str],
        embedded_only: bool,
    ) -> list[sqlite3.Row]:
        query = "SELECT * FROM vector_documents"
        clauses: list[str] = []
        params: list[Any] = []
        if embedded_only:
            clauses.append("embedding_json IS NOT NULL")
        if agent_name:
            clauses.append("agent_name = ?")
            params.append(agent_name)
        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        with self._connect() as conn:
            return list(conn.execute(query, params).fetchall())

    @staticmethod
    def _public_row(row: sqlite3.Row, *, score: Optional[float] = None) -> JsonDict:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}
        record: JsonDict = {
            "doc_id": row["doc_id"],
            "agent_name": row["agent_name"],
            "source_type": row["source_type"],
            "title": row["title"],
            "text": row["text"],
            "metadata": metadata,
            "artifact_id": row["artifact_id"],
            "source_message_id": row["source_message_id"],
            "source_task_type": row["source_task_type"],
            "embedding_model": row["embedding_model"],
            "created_at": row["created_at"],
        }
        if score is not None:
            record["score"] = score
        return record


def get_vector_store(settings: Optional[VectorStoreSettings] = None) -> VectorStore:
    """Construct a ``VectorStore`` for the current settings. Cheap (just
    ensures the schema exists), so no caching is needed and env-var
    overrides in tests take effect immediately."""
    settings = settings or get_settings()
    return VectorStore(settings.db_path)


# ---------------------------------------------------------------------------
# Background (non-blocking) ingestion
# ---------------------------------------------------------------------------

_EXECUTOR: Optional[ThreadPoolExecutor] = None
_EXECUTOR_LOCK = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    with _EXECUTOR_LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vector-ingest")
        return _EXECUTOR


def ingest_artifact(
    record: JsonDict,
    content: str,
    *,
    embedding_client: Optional[OllamaEmbeddingClient] = None,
    store: Optional[VectorStore] = None,
) -> Optional[str]:
    """
    Synchronously ingest one artifact record (as produced by
    ``enterprise_router.agent_artifacts.write_agent_artifact``) into the
    vector store. Returns the stored doc id, or ``None`` when indexing is
    disabled or fails — this function never raises.
    """
    settings = get_settings()
    if not settings.enabled:
        return None
    text = (content or "").strip()
    if not text:
        return None

    try:
        client = embedding_client or OllamaEmbeddingClient()
        vector = client.embed(text)
        vstore = store or get_vector_store(settings)
        doc_id = str(record.get("artifact_id") or "").strip() or f"vec-{uuid.uuid4().hex[:10]}"
        metadata = dict(record.get("metadata") or {})
        metadata.setdefault("artifact_type", record.get("artifact_type"))
        return vstore.add_document(
            doc_id=doc_id,
            agent_name=str(record.get("agent_name") or "unknown"),
            source_type=str(record.get("artifact_type") or "artifact"),
            title=str(record.get("title") or "Untitled artifact"),
            text=text,
            metadata=metadata,
            embedding=vector,
            embedding_model=client.model if vector else "",
            artifact_id=record.get("artifact_id"),
            source_message_id=record.get("source_message_id"),
            source_task_type=record.get("source_task_type"),
            created_at=record.get("created_at"),
        )
    except Exception as exc:  # pragma: no cover - defensive: ingestion must never raise
        logger.warning("Artifact ingestion into the vector store failed: %s", exc)
        return None


def _safe_ingest_artifact(record: JsonDict, content: str) -> None:
    try:
        ingest_artifact(record, content)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Background artifact ingestion failed: %s", exc)


def ingest_artifact_async(record: JsonDict, content: str) -> None:
    """
    Fire-and-forget ingestion hook for
    ``enterprise_router.agent_artifacts.write_agent_artifact``. Never blocks
    the caller and never raises — scheduling failures are logged and
    swallowed so synchronous message routing / artifact persistence is
    unaffected.
    """
    settings = get_settings()
    if not settings.enabled:
        return
    if not settings.async_ingestion:
        _safe_ingest_artifact(record, content)
        return
    try:
        _get_executor().submit(_safe_ingest_artifact, record, content)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not schedule background artifact ingestion: %s", exc)


def ingest_text(
    *,
    agent_name: str,
    source_type: str,
    title: str,
    text: str,
    metadata: Optional[JsonDict] = None,
    artifact_id: Optional[str] = None,
    source_message_id: Optional[str] = None,
    source_task_type: Optional[str] = None,
    embedding_client: Optional[OllamaEmbeddingClient] = None,
    store: Optional[VectorStore] = None,
) -> Optional[str]:
    """General-purpose synchronous ingestion for text that is not an agent
    artifact record — e.g. Engineering code snippets or PM feature
    requirements. Never raises."""
    settings = get_settings()
    if not settings.enabled:
        return None
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    try:
        client = embedding_client or OllamaEmbeddingClient()
        vector = client.embed(cleaned)
        vstore = store or get_vector_store(settings)
        doc_id = f"vec-{uuid.uuid4().hex[:10]}"
        return vstore.add_document(
            doc_id=doc_id,
            agent_name=agent_name,
            source_type=source_type,
            title=title,
            text=cleaned,
            metadata=metadata or {},
            embedding=vector,
            embedding_model=client.model if vector else "",
            artifact_id=artifact_id,
            source_message_id=source_message_id,
            source_task_type=source_task_type,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Text ingestion into the vector store failed: %s", exc)
        return None


def ingest_text_async(**kwargs: Any) -> None:
    """Fire-and-forget variant of :func:`ingest_text`."""
    settings = get_settings()
    if not settings.enabled:
        return
    if not settings.async_ingestion:
        try:
            ingest_text(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Background text ingestion failed: %s", exc)
        return
    try:
        _get_executor().submit(_safe_ingest_text, kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not schedule background text ingestion: %s", exc)


def _safe_ingest_text(kwargs: JsonDict) -> None:
    try:
        ingest_text(**kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Background text ingestion failed: %s", exc)


# ---------------------------------------------------------------------------
# RAG retrieval utilities for agent task handlers
# ---------------------------------------------------------------------------


def semantic_search(
    query: str,
    *,
    top_k: Optional[int] = None,
    agent_name: Optional[str] = None,
    source_type: Optional[str] = None,
    embedding_client: Optional[OllamaEmbeddingClient] = None,
    store: Optional[VectorStore] = None,
) -> list[JsonDict]:
    """
    Semantic / conceptual search over indexed documents. Returns ``[]``
    (never raises) when the vector store is disabled, empty, or the local
    embedding service is unreachable.
    """
    settings = get_settings()
    if not settings.enabled:
        return []
    cleaned = (query or "").strip()
    if not cleaned:
        return []

    try:
        client = embedding_client or OllamaEmbeddingClient()
        vector = client.embed(cleaned)
        if vector is None:
            return []
        vstore = store or get_vector_store(settings)
        return vstore.similarity_search(
            vector,
            top_k=top_k if top_k is not None else settings.default_top_k,
            agent_name=agent_name,
            source_type=source_type,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Semantic search failed: %s", exc)
        return []


def retrieve_rag_context(
    query: str,
    *,
    top_k: Optional[int] = None,
    agent_name: Optional[str] = None,
    source_type: Optional[str] = None,
    max_chars: int = 600,
    embedding_client: Optional[OllamaEmbeddingClient] = None,
    store: Optional[VectorStore] = None,
) -> list[JsonDict]:
    """
    RAG retrieval helper for agent task handlers (CEO strategic reasoning,
    Engineering spec/code search, PM roadmap cross-referencing). Returns a
    list of trimmed, prompt-safe context snippets — plain data, never a
    ``message_schema.Message`` field, so callers are free to fold it into a
    prompt string or an envelope's ``context``/``payload`` dict without risk
    of corrupting the envelope structure.
    """
    hits = semantic_search(
        query,
        top_k=top_k,
        agent_name=agent_name,
        source_type=source_type,
        embedding_client=embedding_client,
        store=store,
    )
    context: list[JsonDict] = []
    for hit in hits:
        text = str(hit.get("text") or "")
        context.append(
            {
                "doc_id": hit.get("doc_id"),
                "artifact_id": hit.get("artifact_id"),
                "agent_name": hit.get("agent_name"),
                "source_type": hit.get("source_type"),
                "title": hit.get("title"),
                "score": hit.get("score"),
                "snippet": text[: max(0, max_chars)].strip(),
                "created_at": hit.get("created_at"),
            }
        )
    return context


def format_rag_context_block(
    hits: list[JsonDict], *, header: str = "Relevant prior context (semantic retrieval)"
) -> str:
    """Render retrieved snippets as a plain-text block suitable for
    prepending to an LLM prompt. Returns ``""`` for an empty/None list."""
    if not hits:
        return ""
    lines = [f"## {header}"]
    for hit in hits:
        title = str(hit.get("title") or "Untitled")
        agent = str(hit.get("agent_name") or "unknown")
        score = hit.get("score")
        score_text = f"{score:.2f}" if isinstance(score, (int, float)) else "n/a"
        snippet = str(hit.get("snippet") or hit.get("text") or "").strip()
        lines.append(f"- [{agent}] {title} (similarity {score_text}): {snippet}")
    return "\n".join(lines)


def vector_store_stats() -> JsonDict:
    """Lightweight status snapshot for observability/API surfaces (mirrors
    the ``/health`` style of ``enterprise_router/api.py``)."""
    settings = get_settings()
    base: JsonDict = {
        "enabled": settings.enabled,
        "embedding_model": settings.embedding_model,
        "embedding_url": settings.embedding_url,
        "db_path": settings.db_path,
        "document_count": 0,
        "embedded_document_count": 0,
    }
    if not settings.enabled:
        return base
    try:
        store = get_vector_store(settings)
        base["document_count"] = store.count()
        base["embedded_document_count"] = store.count(embedded_only=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not read vector store stats: %s", exc)
        base["error"] = str(exc)
    return base
