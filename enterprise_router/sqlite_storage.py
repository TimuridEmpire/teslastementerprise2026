from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from .models import AgentApiKeyRecord, AgentRecord, MessageEnvelope, RegistrationRequest
from .router_storage import RouterStorage


class SQLiteStorage(RouterStorage):
    """SQLite-backed router persistence (agents, queue, leases, audit)."""

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
                CREATE TABLE IF NOT EXISTS agents (
                    agent_name TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    hierarchy_level INTEGER NOT NULL DEFAULT 0,
                    trust_level INTEGER NOT NULL DEFAULT 0,
                    file_path TEXT,
                    endpoint TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    allowed_senders TEXT NOT NULL DEFAULT '[]',
                    allowed_task_types TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS registrations (
                    agent_name TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    payload_json TEXT NOT NULL,
                    token_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    rejection_reason TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS api_keys (
                    agent_name TEXT PRIMARY KEY,
                    key_hash TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT 'default',
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    envelope_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS queue (
                    message_id TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'queued',
                    priority INTEGER NOT NULL DEFAULT 0,
                    dedupe_key TEXT,
                    lease_until TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    ttl_expires_at TEXT,
                    routing_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT NOT NULL DEFAULT '',
                    enqueued_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (message_id, recipient)
                );
                CREATE INDEX IF NOT EXISTS idx_queue_fetch
                    ON queue(recipient, state, priority DESC, enqueued_at);
                CREATE INDEX IF NOT EXISTS idx_queue_dedupe
                    ON queue(recipient, sender, task_type, dedupe_key);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    subject_id TEXT,
                    actor TEXT NOT NULL DEFAULT '',
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dead_letter (
                    message_id TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    error TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    envelope_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (message_id, recipient)
                );
                """
            )
            conn.commit()

    def _row_agent(self, row: sqlite3.Row) -> AgentRecord:
        return AgentRecord(
            agent_name=row["agent_name"],
            role=row["role"],
            hierarchy_level=int(row["hierarchy_level"]),
            trust_level=int(row["trust_level"]),
            file_path=row["file_path"],
            endpoint=row["endpoint"],
            active=bool(row["active"]),
            allowed_senders=json.loads(row["allowed_senders"] or "[]"),
            allowed_task_types=json.loads(row["allowed_task_types"] or "[]"),
        )

    def _queue_record(self, row: sqlite3.Row) -> dict[str, Any]:
        envelope = json.loads(row["envelope_json"])
        return {
            "message_id": row["message_id"],
            "recipient": row["recipient"],
            "sender": row["sender"],
            "task_type": row["task_type"],
            "state": row["state"],
            "priority": int(row["priority"]),
            "attempts": int(row["attempts"]),
            "dedupe_key": row["dedupe_key"],
            "lease_until": row["lease_until"],
            "ttl_expires_at": row["ttl_expires_at"],
            "error": row["error"],
            "routing": json.loads(row["routing_json"] or "{}"),
            "message": envelope,
        }

    def register_agent(self, agent: AgentRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agents (
                    agent_name, role, hierarchy_level, trust_level,
                    file_path, endpoint, active, allowed_senders, allowed_task_types
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_name) DO UPDATE SET
                    role=excluded.role,
                    hierarchy_level=excluded.hierarchy_level,
                    trust_level=excluded.trust_level,
                    file_path=excluded.file_path,
                    endpoint=excluded.endpoint,
                    active=excluded.active,
                    allowed_senders=excluded.allowed_senders,
                    allowed_task_types=excluded.allowed_task_types
                """,
                (
                    agent.agent_name,
                    agent.role,
                    agent.hierarchy_level,
                    agent.trust_level,
                    agent.file_path,
                    agent.endpoint,
                    1 if agent.active else 0,
                    json.dumps(agent.allowed_senders),
                    json.dumps(agent.allowed_task_types),
                ),
            )
            conn.commit()

    def get_agent(self, agent_name: str) -> AgentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE agent_name = ?", (agent_name,)
            ).fetchone()
        return self._row_agent(row) if row else None

    def list_agents(self, status: str | None = None) -> list[AgentRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM agents ORDER BY agent_name").fetchall()
        agents = [self._row_agent(r) for r in rows]
        if status == "active":
            return [a for a in agents if a.active]
        if status == "inactive":
            return [a for a in agents if not a.active]
        return agents

    def request_registration(self, req: RegistrationRequest, token_hash: str) -> str:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            "role": req.role,
            "file_path": req.file_path,
            "endpoint": req.endpoint,
            "metadata": req.metadata,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO registrations (
                    agent_name, role, status, payload_json, token_hash, created_at
                ) VALUES (?, ?, 'pending', ?, ?, ?)
                ON CONFLICT(agent_name) DO UPDATE SET
                    role=excluded.role,
                    status='pending',
                    payload_json=excluded.payload_json,
                    token_hash=excluded.token_hash,
                    created_at=excluded.created_at,
                    reviewed_at=NULL,
                    reviewed_by=NULL,
                    rejection_reason=''
                """,
                (req.agent_name, req.role, json.dumps(payload), token_hash, now),
            )
            conn.commit()
        return req.agent_name

    def get_registration_request(self, agent_name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM registrations WHERE agent_name = ?", (agent_name,)
            ).fetchone()
        if not row:
            return None
        return {
            "agent_name": row["agent_name"],
            "role": row["role"],
            "status": row["status"],
            "token_hash": row["token_hash"],
            "created_at": row["created_at"],
            "reviewed_at": row["reviewed_at"],
            "reviewed_by": row["reviewed_by"],
            "rejection_reason": row["rejection_reason"],
            "payload": json.loads(row["payload_json"] or "{}"),
        }

    def list_registration_requests(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT agent_name FROM registrations WHERE status = ? ORDER BY created_at",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT agent_name FROM registrations ORDER BY created_at"
                ).fetchall()
        return [
            rec
            for r in rows
            if (rec := self.get_registration_request(r["agent_name"])) is not None
        ]

    def update_registration_status(
        self,
        agent_name: str,
        status: str,
        reviewed_at: str,
        reviewed_by: str,
        rejection_reason: str = "",
    ) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE registrations
                SET status=?, reviewed_at=?, reviewed_by=?, rejection_reason=?
                WHERE agent_name=?
                """,
                (status, reviewed_at, reviewed_by, rejection_reason, agent_name),
            )
            conn.commit()
            return cur.rowcount > 0

    def find_message_by_dedupe(
        self, sender: str, recipient: str, task_type: str, dedupe_key: str
    ) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT message_id FROM queue
                WHERE sender=? AND recipient=? AND task_type=? AND dedupe_key=?
                  AND state IN ('queued', 'leased')
                LIMIT 1
                """,
                (sender, recipient, task_type, dedupe_key),
            ).fetchone()
        return row["message_id"] if row else None

    def insert_message(self, message: MessageEnvelope, routing: dict[str, Any]) -> None:
        now = routing.get("enqueued_at") or routing.get("now") or ""
        if not now:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        envelope_json = json.dumps(message.to_dict())
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO messages (message_id, envelope_json) VALUES (?, ?)",
                (message.id, envelope_json),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO queue (
                    message_id, recipient, sender, task_type, state, priority,
                    dedupe_key, lease_until, attempts, ttl_expires_at,
                    routing_json, error, enqueued_at, updated_at
                ) VALUES (?, ?, ?, ?, 'queued', ?, ?, NULL, 0, ?, ?, '', ?, ?)
                """,
                (
                    message.id,
                    message.recipient,
                    message.sender,
                    message.task_type,
                    int(routing.get("priority", 0)),
                    routing.get("dedupe_key"),
                    routing.get("ttl_expires_at"),
                    json.dumps(routing),
                    now,
                    now,
                ),
            )
            conn.commit()

    def get_queue_records(
        self,
        recipient: str,
        sender: str | None = None,
        task_type: str | None = None,
        min_priority: int | None = None,
        limit: int | None = None,
        pending_only: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = ["q.recipient = ?"]
        params: list[Any] = [recipient]
        if pending_only:
            clauses.append("q.state = 'queued'")
        if sender:
            clauses.append("q.sender = ?")
            params.append(sender)
        if task_type:
            clauses.append("q.task_type = ?")
            params.append(task_type)
        if min_priority is not None:
            clauses.append("q.priority >= ?")
            params.append(min_priority)
        sql = f"""
            SELECT q.*, m.envelope_json
            FROM queue q
            JOIN messages m ON m.message_id = q.message_id
            WHERE {' AND '.join(clauses)}
            ORDER BY q.priority DESC, q.enqueued_at
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._queue_record(r) for r in rows]

    def lease_next_message(
        self, recipient: str, lease_until: str
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT q.*, m.envelope_json
                FROM queue q
                JOIN messages m ON m.message_id = q.message_id
                WHERE q.recipient = ? AND q.state = 'queued'
                ORDER BY q.priority DESC, q.enqueued_at
                LIMIT 1
                """,
                (recipient,),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                """
                UPDATE queue
                SET state='leased', lease_until=?, updated_at=?
                WHERE message_id=? AND recipient=?
                """,
                (lease_until, lease_until, row["message_id"], recipient),
            )
            conn.commit()
        rec = self._queue_record(row)
        rec["state"] = "leased"
        rec["lease_until"] = lease_until
        return rec

    def get_message_state(
        self, message_id: str, recipient: str
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT q.*, m.envelope_json
                FROM queue q
                JOIN messages m ON m.message_id = q.message_id
                WHERE q.message_id=? AND q.recipient=?
                """,
                (message_id, recipient),
            ).fetchone()
        return self._queue_record(row) if row else None

    def mark_message_done(self, message_id: str, now: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE queue SET state='done', updated_at=?, lease_until=NULL WHERE message_id=?",
                (now, message_id),
            )
            conn.execute("DELETE FROM queue WHERE message_id=? AND state='done'", (message_id,))
            conn.commit()

    def requeue_message(
        self, message_id: str, error: str, attempts: int, now: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE queue
                SET state='queued', error=?, attempts=?, lease_until=NULL, updated_at=?
                WHERE message_id=?
                """,
                (error, attempts, now, message_id),
            )
            conn.commit()

    def dead_letter_message(
        self, message_id: str, error: str, attempts: int, now: str
    ) -> None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT q.recipient, m.envelope_json
                FROM queue q
                JOIN messages m ON m.message_id = q.message_id
                WHERE q.message_id=?
                """,
                (message_id,),
            ).fetchone()
            if not row:
                return
            conn.execute(
                """
                INSERT OR REPLACE INTO dead_letter
                (message_id, recipient, error, attempts, envelope_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (message_id, row["recipient"], error, attempts, row["envelope_json"], now),
            )
            conn.execute("DELETE FROM queue WHERE message_id=?", (message_id,))
            conn.commit()

    def requeue_expired_leases(
        self, now: str, recipient: str | None = None
    ) -> list[dict[str, Any]]:
        clauses = ["state='leased'", "lease_until IS NOT NULL", "lease_until < ?"]
        params: list[Any] = [now]
        if recipient:
            clauses.append("recipient = ?")
            params.append(recipient)
        sql = f"SELECT message_id, recipient FROM queue WHERE {' AND '.join(clauses)}"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            for row in rows:
                conn.execute(
                    """
                    UPDATE queue
                    SET state='queued', lease_until=NULL, updated_at=?
                    WHERE message_id=? AND recipient=?
                    """,
                    (now, row["message_id"], row["recipient"]),
                )
            conn.commit()
        return [{"message_id": r["message_id"], "recipient": r["recipient"]} for r in rows]

    def expire_ttl_messages(
        self, now: str, recipient: str | None = None
    ) -> list[dict[str, Any]]:
        clauses = [
            "ttl_expires_at IS NOT NULL",
            "ttl_expires_at < ?",
            "state IN ('queued', 'leased')",
        ]
        params: list[Any] = [now]
        if recipient:
            clauses.append("recipient = ?")
            params.append(recipient)
        sql = f"SELECT message_id, recipient, attempts FROM queue WHERE {' AND '.join(clauses)}"
        expired: list[dict[str, Any]] = []
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            for row in rows:
                attempts = int(row["attempts"]) + 1
                self.dead_letter_message(
                    row["message_id"],
                    "TTL expired",
                    attempts,
                    now,
                )
                expired.append(
                    {
                        "message_id": row["message_id"],
                        "recipient": row["recipient"],
                    }
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
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit (event_type, subject_id, actor, details_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_type, subject_id, actor, json.dumps(details), created_at),
            )
            conn.commit()

    def list_audit_log(
        self, limit: int = 50, subject_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if subject_id:
                rows = conn.execute(
                    """
                    SELECT * FROM audit WHERE subject_id = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (subject_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [
            {
                "event_type": r["event_type"],
                "subject_id": r["subject_id"],
                "actor": r["actor"],
                "details": json.loads(r["details_json"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def store_api_key(self, record: AgentApiKeyRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO api_keys
                (agent_name, key_hash, label, created_at, last_used_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.agent_name,
                    record.key_hash,
                    record.label,
                    record.created_at,
                    record.last_used_at,
                ),
            )
            conn.commit()

    def get_api_key(self, agent_name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE agent_name = ?", (agent_name,)
            ).fetchone()
        if not row:
            return None
        return {
            "agent_name": row["agent_name"],
            "key_hash": row["key_hash"],
            "label": row["label"],
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
        }

    def touch_api_key(self, agent_name: str, last_used_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE api_keys SET last_used_at=? WHERE agent_name=?",
                (last_used_at, agent_name),
            )
            conn.commit()
