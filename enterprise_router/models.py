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
        return cls(
            priority=int(raw.get("priority", 0) or 0),
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
    visible_at: str = ""
    lease_owner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "message_id": self.message_id,
            "recipient": self.recipient,
            "priority": self.priority,
            "state": self.state,
            "message": self.envelope.to_dict(),
        }
