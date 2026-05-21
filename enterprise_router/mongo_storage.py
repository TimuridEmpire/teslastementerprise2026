from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from enterprise_paths import inter_agent_mongo_db_name, inter_agent_mongo_uri

from .models import AgentApiKeyRecord, AgentRecord, MessageEnvelope, RegistrationRequest
from .router_storage import RouterStorage


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class MongoStorage(RouterStorage):
    """MongoDB-backed router persistence (same contract as SQLite)."""

    def __init__(
        self,
        uri: str | None = None,
        db_name: str | None = None,
    ) -> None:
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise ImportError("MongoStorage requires pymongo.") from exc

        self._client = MongoClient(uri or inter_agent_mongo_uri())
        self._db = self._client[db_name or inter_agent_mongo_db_name()]
        self._agents = self._db["router_agents"]
        self._registrations = self._db["router_registrations"]
        self._api_keys = self._db["router_api_keys"]
        self._messages = self._db["router_messages"]
        self._queue = self._db["router_queue"]
        self._audit = self._db["router_audit"]
        self._dead_letter = self._db["router_dead_letter"]
        self._agents.create_index("agent_name", unique=True)
        self._queue.create_index([("recipient", 1), ("state", 1), ("priority", -1)])

    def register_agent(self, agent: AgentRecord) -> None:
        doc = agent.to_dict()
        doc["_id"] = agent.agent_name
        self._agents.replace_one({"_id": agent.agent_name}, doc, upsert=True)

    def get_agent(self, agent_name: str) -> AgentRecord | None:
        doc = self._agents.find_one({"_id": agent_name}) or self._agents.find_one(
            {"agent_name": agent_name}
        )
        if not doc:
            return None
        return AgentRecord(
            agent_name=doc["agent_name"],
            role=doc["role"],
            hierarchy_level=int(doc.get("hierarchy_level", 0)),
            trust_level=int(doc.get("trust_level", 0)),
            file_path=doc.get("file_path"),
            endpoint=doc.get("endpoint"),
            active=bool(doc.get("active", True)),
            allowed_senders=list(doc.get("allowed_senders") or []),
            allowed_task_types=list(doc.get("allowed_task_types") or []),
        )

    def list_agents(self, status: str | None = None) -> list[AgentRecord]:
        agents: list[AgentRecord] = []
        for d in self._agents.find({}):
            name = d.get("agent_name") or d.get("_id")
            if not name:
                continue
            agent = self.get_agent(str(name))
            if agent is not None:
                agents.append(agent)
        if status == "active":
            return [a for a in agents if a.active]
        if status == "inactive":
            return [a for a in agents if not a.active]
        return agents

    def request_registration(self, req: RegistrationRequest, token_hash: str) -> str:
        payload = {
            "role": req.role,
            "file_path": req.file_path,
            "endpoint": req.endpoint,
            "metadata": req.metadata,
        }
        self._registrations.replace_one(
            {"_id": req.agent_name},
            {
                "_id": req.agent_name,
                "agent_name": req.agent_name,
                "role": req.role,
                "status": "pending",
                "payload": payload,
                "token_hash": token_hash,
                "created_at": _utc_now(),
            },
            upsert=True,
        )
        return req.agent_name

    def get_registration_request(self, agent_name: str) -> dict[str, Any] | None:
        doc = self._registrations.find_one({"_id": agent_name})
        if not doc:
            return None
        return {
            "agent_name": doc["agent_name"],
            "role": doc["role"],
            "status": doc["status"],
            "token_hash": doc.get("token_hash", ""),
            "created_at": doc.get("created_at"),
            "reviewed_at": doc.get("reviewed_at"),
            "reviewed_by": doc.get("reviewed_by"),
            "rejection_reason": doc.get("rejection_reason", ""),
            "payload": doc.get("payload") or {},
        }

    def list_registration_requests(self, status: str | None = None) -> list[dict[str, Any]]:
        query = {"status": status} if status else {}
        return [
            rec
            for doc in self._registrations.find(query).sort("created_at", 1)
            if (rec := self.get_registration_request(doc["agent_name"])) is not None
        ]

    def update_registration_status(
        self,
        agent_name: str,
        status: str,
        reviewed_at: str,
        reviewed_by: str,
        rejection_reason: str = "",
    ) -> bool:
        result = self._registrations.update_one(
            {"_id": agent_name},
            {
                "$set": {
                    "status": status,
                    "reviewed_at": reviewed_at,
                    "reviewed_by": reviewed_by,
                    "rejection_reason": rejection_reason,
                }
            },
        )
        return result.modified_count > 0

    def find_message_by_dedupe(
        self, sender: str, recipient: str, task_type: str, dedupe_key: str
    ) -> str | None:
        doc = self._queue.find_one(
            {
                "sender": sender,
                "recipient": recipient,
                "task_type": task_type,
                "dedupe_key": dedupe_key,
                "state": {"$in": ["queued", "leased"]},
            },
            projection={"message_id": 1},
        )
        return doc["message_id"] if doc else None

    def insert_message(self, message: MessageEnvelope, routing: dict[str, Any]) -> None:
        now = routing.get("enqueued_at") or _utc_now()
        self._messages.replace_one(
            {"_id": message.id},
            {"_id": message.id, "envelope": message.to_dict()},
            upsert=True,
        )
        self._queue.replace_one(
            {"message_id": message.id, "recipient": message.recipient},
            {
                "message_id": message.id,
                "recipient": message.recipient,
                "sender": message.sender,
                "task_type": message.task_type,
                "state": "queued",
                "priority": int(routing.get("priority", 0)),
                "dedupe_key": routing.get("dedupe_key"),
                "lease_until": None,
                "attempts": 0,
                "ttl_expires_at": routing.get("ttl_expires_at"),
                "routing": routing,
                "error": "",
                "enqueued_at": now,
                "updated_at": now,
            },
            upsert=True,
        )

    def get_queue_records(
        self,
        recipient: str,
        sender: str | None = None,
        task_type: str | None = None,
        min_priority: int | None = None,
        limit: int | None = None,
        pending_only: bool = False,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"recipient": recipient}
        if pending_only:
            query["state"] = "queued"
        if sender:
            query["sender"] = sender
        if task_type:
            query["task_type"] = task_type
        if min_priority is not None:
            query["priority"] = {"$gte": min_priority}
        cursor = self._queue.find(query).sort(
            [("priority", -1), ("enqueued_at", 1)]
        )
        if limit is not None:
            cursor = cursor.limit(limit)
        return [self._hydrate_queue_doc(doc) for doc in cursor]

    def _hydrate_queue_doc(self, doc: dict[str, Any]) -> dict[str, Any]:
        msg_doc = self._messages.find_one({"_id": doc["message_id"]})
        envelope = (msg_doc or {}).get("envelope") or {}
        return {
            "message_id": doc["message_id"],
            "recipient": doc["recipient"],
            "sender": doc["sender"],
            "task_type": doc["task_type"],
            "state": doc["state"],
            "priority": int(doc.get("priority", 0)),
            "attempts": int(doc.get("attempts", 0)),
            "dedupe_key": doc.get("dedupe_key"),
            "lease_until": doc.get("lease_until"),
            "ttl_expires_at": doc.get("ttl_expires_at"),
            "error": doc.get("error", ""),
            "routing": doc.get("routing") or {},
            "message": envelope,
        }

    def lease_next_message(
        self, recipient: str, lease_until: str
    ) -> dict[str, Any] | None:
        doc = self._queue.find_one_and_update(
            {"recipient": recipient, "state": "queued"},
            {"$set": {"state": "leased", "lease_until": lease_until, "updated_at": lease_until}},
            sort=[("priority", -1), ("enqueued_at", 1)],
        )
        if not doc:
            return None
        return self._hydrate_queue_doc(doc)

    def get_message_state(
        self, message_id: str, recipient: str
    ) -> dict[str, Any] | None:
        doc = self._queue.find_one({"message_id": message_id, "recipient": recipient})
        return self._hydrate_queue_doc(doc) if doc else None

    def mark_message_done(self, message_id: str, now: str) -> None:
        self._queue.delete_many({"message_id": message_id})

    def requeue_message(
        self, message_id: str, error: str, attempts: int, now: str
    ) -> None:
        self._queue.update_many(
            {"message_id": message_id},
            {
                "$set": {
                    "state": "queued",
                    "error": error,
                    "attempts": attempts,
                    "lease_until": None,
                    "updated_at": now,
                }
            },
        )

    def dead_letter_message(
        self, message_id: str, error: str, attempts: int, now: str
    ) -> None:
        doc = self._queue.find_one({"message_id": message_id})
        if not doc:
            return
        msg_doc = self._messages.find_one({"_id": message_id})
        envelope = json.dumps((msg_doc or {}).get("envelope") or {})
        self._dead_letter.replace_one(
            {"message_id": message_id, "recipient": doc["recipient"]},
            {
                "message_id": message_id,
                "recipient": doc["recipient"],
                "error": error,
                "attempts": attempts,
                "envelope_json": envelope,
                "created_at": now,
            },
            upsert=True,
        )
        self._queue.delete_many({"message_id": message_id})

    def requeue_expired_leases(
        self, now: str, recipient: str | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "state": "leased",
            "lease_until": {"$lt": now},
        }
        if recipient:
            query["recipient"] = recipient
        docs = list(self._queue.find(query))
        for doc in docs:
            self._queue.update_one(
                {"_id": doc["_id"]},
                {"$set": {"state": "queued", "lease_until": None, "updated_at": now}},
            )
        return [
            {"message_id": d["message_id"], "recipient": d["recipient"]} for d in docs
        ]

    def expire_ttl_messages(
        self, now: str, recipient: str | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "ttl_expires_at": {"$lt": now},
            "state": {"$in": ["queued", "leased"]},
        }
        if recipient:
            query["recipient"] = recipient
        expired: list[dict[str, Any]] = []
        for doc in self._queue.find(query):
            attempts = int(doc.get("attempts", 0)) + 1
            self.dead_letter_message(doc["message_id"], "TTL expired", attempts, now)
            expired.append(
                {"message_id": doc["message_id"], "recipient": doc["recipient"]}
            )
        return expired

    def log_audit(
        self,
        event_type: str,
        subject_id: str,
        actor: str,
        details: dict[str, Any],
        created_at: str,
    ) -> None:
        self._audit.insert_one(
            {
                "event_type": event_type,
                "subject_id": subject_id,
                "actor": actor,
                "details": details,
                "created_at": created_at,
            }
        )

    def list_audit_log(
        self, limit: int = 50, subject_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = {"subject_id": subject_id} if subject_id else {}
        return [
            {
                "event_type": d["event_type"],
                "subject_id": d.get("subject_id"),
                "actor": d.get("actor", ""),
                "details": d.get("details") or {},
                "created_at": d.get("created_at"),
            }
            for d in self._audit.find(query).sort("created_at", -1).limit(limit)
        ]

    def store_api_key(self, record: AgentApiKeyRecord) -> None:
        self._api_keys.replace_one(
            {"_id": record.agent_name},
            {
                "_id": record.agent_name,
                "agent_name": record.agent_name,
                "key_hash": record.key_hash,
                "label": record.label,
                "created_at": record.created_at,
                "last_used_at": record.last_used_at,
            },
            upsert=True,
        )

    def get_api_key(self, agent_name: str) -> dict[str, Any] | None:
        doc = self._api_keys.find_one({"_id": agent_name})
        if not doc:
            return None
        return {
            "agent_name": doc["agent_name"],
            "key_hash": doc["key_hash"],
            "label": doc.get("label", "default"),
            "created_at": doc.get("created_at"),
            "last_used_at": doc.get("last_used_at"),
        }

    def touch_api_key(self, agent_name: str, last_used_at: str) -> None:
        self._api_keys.update_one(
            {"_id": agent_name}, {"$set": {"last_used_at": last_used_at}}
        )
