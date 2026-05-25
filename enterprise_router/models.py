from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from message_schema import Message

# Router storage and API use the shared enterprise envelope type.
MessageEnvelope = Message


@dataclass
class RegistrationRequest:
    agent_name: str
    role: str
    secret_token: str
    file_path: str | None = None
    endpoint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentApiKeyRecord:
    agent_name: str
    key_hash: str
    label: str = "default"
    created_at: str = ""
    last_used_at: str | None = None


@dataclass
class AgentRecord:
    agent_name: str
    role: str
    hierarchy_level: int = 0
    trust_level: int = 0
    file_path: str | None = None
    endpoint: str | None = None
    active: bool = True
    allowed_senders: list[str] = field(default_factory=list)
    allowed_task_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RoutingHints:
    priority: int = 0
    requires_response: bool = False
    ttl_seconds: int | None = None
    dedupe_key: str | None = None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> RoutingHints:
        if not raw:
            return cls()
        priority = raw.get("priority")
        if priority is None:
            urgency = str(raw.get("urgency") or "").strip().lower()
            priority = {
                "critical": 200,
                "urgent": 175,
                "high": 150,
                "normal": 100,
                "medium": 100,
                "low": 50,
            }.get(urgency, 0)
        return cls(
            priority=int(priority or 0),
            requires_response=bool(raw.get("requires_response", False)),
            ttl_seconds=raw.get("ttl_seconds"),
            dedupe_key=raw.get("dedupe_key"),
        )


@dataclass
class QueuedMessage:
    queue_id: str
    message_id: str
    recipient: str
    envelope: MessageEnvelope
    priority: int = 0
    state: str = "queued"
    attempts: int = 0
    lease_until: str | None = None
    blocked_reason: str = ""
    ttl_seconds: int | None = None
    dedupe_key: str | None = None
    enqueued_at: str | None = None
    ttl_expires_at: str | None = None
    visible_at: str | None = None

    def _delivery_state(self) -> str:
        if self.state == "queued":
            return "pending"
        return self.state

    def to_dict(self) -> dict[str, Any]:
        context = self.envelope.context or {}
        return {
            "queue_id": self.queue_id,
            "message_id": self.message_id,
            "recipient": self.recipient,
            "envelope": self.envelope.to_dict(),
            "computed_priority": self.priority,
            "attempt_count": self.attempts,
            "lease_until": self.lease_until,
            "delivery_state": self._delivery_state(),
            "blocked_reason": self.blocked_reason,
            "enqueued_at": self.enqueued_at,
            "ttl_expires_at": self.ttl_expires_at,
            "visible_at": self.visible_at,
            "provenance_source": context.get("provenance_source"),
            "provenance_agent": context.get("provenance_agent"),
            "provenance_trust_level": context.get("provenance_trust_level"),
            "ttl_seconds": self.ttl_seconds,
            "dedupe_key": self.dedupe_key,
        }
