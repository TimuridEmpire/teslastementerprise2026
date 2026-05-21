from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING
import hashlib

# We trust these imported functions to securely handle the .env logic now
from enterprise_paths import inter_agent_mongo_db_name, inter_agent_mongo_uri
from message_bus import normalize_envelope

if TYPE_CHECKING:
    from agent_backlog import AgentBacklog

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_db_name(name: str, max_bytes: int = 38) -> str:
    encoded_len = len(name.encode("utf-8"))
    if encoded_len <= max_bytes:
        return name
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    keep = max_bytes - len("ia_") - len(digest) - 1
    prefix = name.encode("utf-8")[:keep].decode("utf-8", errors="ignore")
    return f"ia_{prefix}_{digest}"

class InterAgentMongoStore:
    """
    Stores envelopes and per-recipient FIFO inboxes in MongoDB.
    """

    def __init__(
        self,
        mongo_uri: Optional[str] = None, 
        db_name: Optional[str] = None,
        *,
        mirror_backlog: Optional["AgentBacklog"] = None,
    ):
        try:
            from pymongo import MongoClient
            from pymongo.errors import DuplicateKeyError
        except ImportError as e:
            raise ImportError(
                "InterAgentMongoStore requires pymongo. Install: pip install pymongo"
            ) from e

        # If a URI wasn't explicitly passed, call the function.
        # The function will automatically check the .env file for us!
        uri = mongo_uri if mongo_uri is not None else inter_agent_mongo_uri()
        name = db_name if db_name is not None else inter_agent_mongo_db_name()

        normalized_name = _normalize_db_name(name)

        self._mirror = mirror_backlog
        self._DuplicateKeyError = DuplicateKeyError
        
        self._client = MongoClient(uri)
        self._db = self._client[normalized_name]

        self._envelopes = self._db["envelopes"]
        self._inbox = self._db["inbox"]
        self._envelopes.create_index("id", unique=True)
        self._inbox.create_index([("recipient", 1), ("enqueued_at", 1)])

    def record_and_enqueue(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize the envelope, persist to ``envelopes`` (idempotent on id),
        enqueue for ``recipient``, optionally mirror to SQLite.
        Returns a small status dict for the HTTP layer.
        """
        env = normalize_envelope(raw)
        eid = (env.get("id") or "").strip()
        recipient = (env.get("recipient") or "").strip()
        if not eid:
            return {"ok": False, "error": "envelope id is required", "id": ""}
        if not recipient:
            return {"ok": False, "error": "recipient is required", "id": eid}

        doc = {**env, "_stored_at": _utc_now()}
        duplicate = False
        try:
            self._envelopes.insert_one(doc)
        except self._DuplicateKeyError:
            duplicate = True

        if not duplicate:
            self._inbox.insert_one(
                {
                    "recipient": recipient,
                    "envelope": env,
                    "enqueued_at": _utc_now(),
                }
            )

        if self._mirror is not None:
            self._mirror.record_interaction(env)

        return {
            "ok": True,
            "id": eid,
            "duplicate": duplicate,
            "queued": not duplicate,
        }

    def pop_next_for_recipient(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """FIFO: remove and return the next envelope for this agent, or None."""
        name = (agent_name or "").strip()
        if not name:
            return None
        row = self._inbox.find_one_and_delete(
            {"recipient": name},
            sort=[("enqueued_at", 1)],
        )
        if not row:
            return None
        env = row.get("envelope")
        return env if isinstance(env, dict) else None

    def pending_count(self, agent_name: str) -> int:
        name = (agent_name or "").strip()
        if not name:
            return 0
        return self._inbox.count_documents({"recipient": name})

    def close(self) -> None:
        self._client.close()


def inter_agent_store_from_env(
    *,
    mirror_sqlite: bool = False,
) -> InterAgentMongoStore:
    """
    Factory using environment defaults. If mirror_sqlite is True, also append to
    the canonical SQLite backlog (same file as in-process agents).
    """
    from agent_backlog import AgentBacklog

    mirror = AgentBacklog() if mirror_sqlite else None
    return InterAgentMongoStore(mirror_backlog=mirror)
