from __future__ import annotations

import hashlib
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from message_schema import Message, normalize_envelope

from .exceptions import AccessError, RegistrationError, ValidationError
from .models import (
    AgentApiKeyRecord,
    AgentRecord,
    MessageEnvelope,
    QueuedMessage,
    RegistrationRequest,
    RoutingHints,
)
from .router_storage import RouterStorage, create_storage

MAX_NACK_ATTEMPTS = 3
LEASE_SECONDS = 120


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _lease_until(now: datetime | None = None) -> str:
    base = now or datetime.now(timezone.utc)
    return (base + timedelta(seconds=LEASE_SECONDS)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ttl_expires_at(now: datetime, ttl_seconds: int | None) -> str | None:
    if not ttl_seconds:
        return None
    return (now + timedelta(seconds=int(ttl_seconds))).strftime("%Y-%m-%dT%H:%M:%SZ")


class EnterpriseRouter:
    """Registration, API keys, prioritized queues, and audit log."""

    def __init__(
        self,
        *,
        backend: str = "sqlite",
        db_path: str | None = None,
        mongo_uri: str | None = None,
        mongo_db_name: str | None = None,
        shared_secret: str = "change-me-registration",
        storage: RouterStorage | None = None,
    ):
        self.shared_secret = shared_secret
        self._lock = threading.Lock()
        if storage is not None:
            self._storage = storage
        else:
            import os

            default_db = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "enterprise_router.db",
            )
            self._storage = create_storage(
                backend=backend,
                db_path=db_path or default_db,
                mongo_uri=mongo_uri,
                mongo_db_name=mongo_db_name,
            )

    def _audit(self, subject_id: str, event_type: str, details: dict[str, Any], *, actor: str = "system") -> None:
        self._storage.log_audit(event_type, subject_id, actor, details, _utc_now())

    def _check_send_access(self, agent: AgentRecord, envelope: MessageEnvelope) -> None:
        if not agent.active:
            raise AccessError(f"Agent {agent.agent_name!r} is not active.")
        if agent.allowed_senders and envelope.sender not in agent.allowed_senders:
            raise AccessError(
                f"Sender {envelope.sender!r} is not allowed for agent {agent.agent_name!r}."
            )
        if agent.allowed_task_types and envelope.task_type not in agent.allowed_task_types:
            raise AccessError(
                f"Task type {envelope.task_type!r} is not allowed for agent {agent.agent_name!r}."
            )

    def authenticate_agent(self, agent_name: str, api_key: str) -> None:
        name = (agent_name or "").strip()
        if not name or not api_key:
            raise AccessError("Invalid agent credentials.")
        record = self._storage.get_api_key(name)
        if not record or record.get("key_hash") != _hash_key(api_key):
            raise AccessError("Invalid API key.")
        agent = self._storage.get_agent(name)
        if not agent or not agent.active:
            raise AccessError("Agent is not active.")
        self._storage.touch_api_key(name, _utc_now())

    def request_registration(self, request: RegistrationRequest) -> str:
        if request.secret_token != self.shared_secret:
            raise RegistrationError("Invalid registration secret.")
        name = (request.agent_name or "").strip()
        if not name:
            raise ValidationError("agent_name is required.")
        existing = self._storage.get_registration_request(name)
        if existing and existing.get("status") == "pending":
            raise RegistrationError(f"Registration for {name!r} is already pending.")
        token_hash = _hash_key(request.secret_token)
        self._storage.request_registration(request, token_hash)
        self._audit(name, "registration_requested", {"role": request.role})
        return name

    def approve_registration(
        self,
        agent_name: str,
        approver: str,
        *,
        issue_api_key: bool = False,
        key_label: str = "default",
    ) -> str | None:
        name = (agent_name or "").strip()
        row = self._storage.get_registration_request(name)
        if not row:
            raise RegistrationError(f"No registration for {name!r}.")
        if row.get("status") != "pending":
            raise RegistrationError(f"Registration for {name!r} is not pending.")
        now = _utc_now()
        self._storage.update_registration_status(name, "approved", now, approver)
        payload = row.get("payload") or {}
        self.register_agent(
            AgentRecord(
                agent_name=name,
                role=row.get("role", ""),
                file_path=payload.get("file_path"),
                endpoint=payload.get("endpoint"),
            )
        )
        api_key = self.issue_api_key(name, label=key_label) if issue_api_key else None
        self._audit(name, "registration_approved", {"approver": approver}, actor=approver)
        return api_key

    def reject_registration(self, agent_name: str, approver: str, reason: str) -> None:
        name = (agent_name or "").strip()
        row = self._storage.get_registration_request(name)
        if not row or row.get("status") != "pending":
            raise RegistrationError(f"No pending registration for {name!r}.")
        self._storage.update_registration_status(name, "rejected", _utc_now(), approver, reason)
        self._audit(name, "registration_rejected", {"approver": approver, "reason": reason}, actor=approver)

    def list_registration_requests(self, status: str | None = None) -> list[dict[str, Any]]:
        rows = self._storage.list_registration_requests(status=status)
        return [
            {
                "agent_name": r["agent_name"],
                "role": r["role"],
                "status": r["status"],
                "created_at": r.get("created_at"),
                "decided_at": r.get("reviewed_at"),
                "decided_by": r.get("reviewed_by"),
                "reject_reason": r.get("rejection_reason", ""),
                "payload": r.get("payload") or {},
            }
            for r in rows
        ]

    def register_agent(self, record: AgentRecord) -> None:
        name = (record.agent_name or "").strip()
        if not name:
            raise ValidationError("agent_name is required.")
        self._storage.register_agent(record)
        self._audit(name, "agent_registered", record.to_dict())

    def list_agents(self, status: str | None = None) -> list[AgentRecord]:
        return self._storage.list_agents(status=status)

    def issue_api_key(self, agent_name: str, *, label: str = "default") -> str:
        name = (agent_name or "").strip()
        if not self._storage.get_agent(name):
            raise ValidationError(f"Unknown agent {name!r}.")
        raw = secrets.token_urlsafe(32)
        now = _utc_now()
        self._storage.store_api_key(
            AgentApiKeyRecord(
                agent_name=name,
                key_hash=_hash_key(raw),
                label=label,
                created_at=now,
            )
        )
        self._audit(name, "api_key_issued", {"label": label})
        return raw

    def submit_message(self, envelope: MessageEnvelope, hints: RoutingHints) -> str:
        raw = normalize_envelope(envelope)
        env = Message.from_dict(raw)
        eid = (env.id or "").strip()
        recipient = (env.recipient or "").strip()
        sender = (env.sender or "").strip()
        if not eid:
            raise ValidationError("message id is required.")
        if not recipient:
            raise ValidationError("recipient is required.")
        if not sender:
            raise ValidationError("sender is required.")

        agent = self._storage.get_agent(recipient)
        if agent:
            self._check_send_access(agent, env)

        now_dt = datetime.now(timezone.utc)
        now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        routing: dict[str, Any] = {
            "priority": hints.priority,
            "requires_response": hints.requires_response,
            "ttl_seconds": hints.ttl_seconds,
            "dedupe_key": hints.dedupe_key,
            "ttl_expires_at": _ttl_expires_at(now_dt, hints.ttl_seconds),
            "enqueued_at": now,
        }

        if hints.dedupe_key:
            existing = self._storage.find_message_by_dedupe(
                sender, recipient, env.task_type, hints.dedupe_key
            )
            if existing:
                return existing

        with self._lock:
            self._storage.insert_message(env, routing)
        self._audit(eid, "message_submitted", {"recipient": recipient, "sender": sender})
        return eid

    def submit_manager_intervention(
        self,
        *,
        recipient: str,
        instruction: str,
        task_type: str = "MANAGER_INTERVENTION",
        urgency: str = "normal",
        context: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        requires_response: bool = False,
        ttl_seconds: int | None = None,
        dedupe_key: str | None = None,
    ) -> str:
        import uuid

        priority_map = {"low": 0, "normal": 5, "high": 10, "critical": 20}
        envelope = Message.create(
            sender="MANAGER",
            recipient=recipient,
            task_type=task_type,
            context={**(context or {}), "urgency": urgency},
            payload={**(payload or {}), "instruction": instruction},
            message_id=f"mgr-{uuid.uuid4().hex[:8]}",
        )
        envelope.timestamp = _utc_now()
        hints = RoutingHints(
            priority=priority_map.get((urgency or "normal").lower(), 5),
            requires_response=requires_response,
            ttl_seconds=ttl_seconds,
            dedupe_key=dedupe_key,
        )
        return self.submit_message(envelope, hints)

    def _record_to_queued(self, record: dict[str, Any]) -> QueuedMessage:
        msg = record.get("message") or {}
        env = Message.from_dict(msg)
        return QueuedMessage(
            queue_id=record.get("message_id", ""),
            message_id=record.get("message_id", ""),
            recipient=record.get("recipient", ""),
            envelope=env,
            priority=int(record.get("priority", 0)),
            state=record.get("state", "queued"),
            lease_owner=record.get("lease_until"),
        )

    def _maintain_queue(self, recipient: str) -> None:
        now = _utc_now()
        self._storage.requeue_expired_leases(now, recipient)
        self._storage.expire_ttl_messages(now, recipient)

    def peek_messages(
        self,
        recipient: str,
        min_priority: int | None = None,
        sender: str | None = None,
        task_type: str | None = None,
        limit: int = 10,
    ) -> list[QueuedMessage]:
        self._maintain_queue(recipient)
        rows = self._storage.get_queue_records(
            recipient,
            sender=sender,
            task_type=task_type,
            min_priority=min_priority,
            limit=limit,
            pending_only=True,
        )
        return [self._record_to_queued(r) for r in rows]

    def fetch_next(self, recipient: str) -> QueuedMessage | None:
        name = (recipient or "").strip()
        self._maintain_queue(name)
        with self._lock:
            record = self._storage.lease_next_message(name, _lease_until())
        return self._record_to_queued(record) if record else None

    def list_queue(self, recipient: str) -> list[QueuedMessage]:
        return self.peek_messages(recipient, limit=100)

    def ack_message(self, message_id: str, recipient: str) -> None:
        mid = (message_id or "").strip()
        name = (recipient or "").strip()
        state = self._storage.get_message_state(mid, name)
        if not state:
            raise ValidationError(f"No queued message {mid!r} for {name!r}.")
        self._storage.mark_message_done(mid, _utc_now())
        self._audit(mid, "message_acked", {"recipient": name})

    def nack_message(self, message_id: str, recipient: str, reason: str) -> None:
        mid = (message_id or "").strip()
        name = (recipient or "").strip()
        state = self._storage.get_message_state(mid, name)
        if not state:
            raise ValidationError(f"No queued message {mid!r} for {name!r}.")
        attempts = int(state.get("attempts", 0)) + 1
        now = _utc_now()
        if attempts >= MAX_NACK_ATTEMPTS:
            self._storage.dead_letter_message(mid, reason, attempts, now)
        else:
            self._storage.requeue_message(mid, reason, attempts, now)
        self._audit(mid, "message_nacked", {"recipient": name, "reason": reason, "attempts": attempts})

    def list_audit_log(
        self, *, limit: int = 20, subject_id: str | None = None
    ) -> list[dict[str, Any]]:
        return self._storage.list_audit_log(limit=limit, subject_id=subject_id)
