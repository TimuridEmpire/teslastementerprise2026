"""
message_schema.py

Single source of truth for the enterprise agent message envelope.
All inter-agent communication (MessageBus, AgentBacklog, Enterprise Router,
agent transport, and department agents) should build and validate messages here.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

EnvelopeDict = Dict[str, Any]
EnvelopeInput = Union["Message", EnvelopeDict]


@dataclass
class Message:
    id: str
    timestamp: str
    sender: str
    recipient: str
    task_type: str
    context: Dict[str, Any]
    payload: Dict[str, Any]
    status: str
    error: str = ""

    REQUIRED_FIELDS = (
        "id",
        "timestamp",
        "sender",
        "recipient",
        "task_type",
        "context",
        "payload",
        "status",
        "error",
    )

    VALID_STATUSES = {"pending", "in_progress", "done", "error"}

    @staticmethod
    def create(
        sender: str,
        recipient: str,
        task_type: str,
        context: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        *,
        status: str = "pending",
        error: str = "",
        message_id: Optional[str] = None,
    ) -> Message:
        """Factory for a new outbound envelope (UUID + ISO-8601 UTC timestamp)."""
        msg = Message(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            sender=sender,
            recipient=recipient,
            task_type=task_type,
            context=context or {},
            payload=payload or {},
            status=status,
            error=error or "",
        )
        if message_id:
            msg.id = message_id
        return msg

    def to_dict(self) -> EnvelopeDict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: EnvelopeDict, *, validate: bool = True) -> Message:
        data = normalize_envelope(raw, validate=validate)
        return cls(**{k: data[k] for k in cls.REQUIRED_FIELDS})

    @staticmethod
    def validate_envelope(message: EnvelopeDict) -> None:
        missing = [k for k in Message.REQUIRED_FIELDS if k not in message]
        if missing:
            raise ValueError(f"Missing required envelope fields: {missing}")

        if not isinstance(message["context"], dict):
            raise ValueError("Envelope field 'context' must be a dictionary.")

        if not isinstance(message["payload"], dict):
            raise ValueError("Envelope field 'payload' must be a dictionary.")

        if message["status"] not in Message.VALID_STATUSES:
            raise ValueError(
                f"Envelope field 'status' must be one of: {', '.join(Message.VALID_STATUSES)}."
            )


def envelope_dict(message: EnvelopeInput) -> EnvelopeDict:
    """Return a dict for logging/serialization without strict validation."""
    if isinstance(message, Message):
        return message.to_dict()
    return dict(message)


def normalize_envelope(
    raw: EnvelopeInput,
    *,
    validate: bool = True,
) -> EnvelopeDict:
    """
    Canonical envelope dict for persistence and routing.
    Fills missing keys with safe defaults, then optionally validates.
    """
    data = envelope_dict(raw)
    normalized: EnvelopeDict = {
        "id": data.get("id", ""),
        "timestamp": data.get("timestamp", ""),
        "sender": data.get("sender", ""),
        "recipient": data.get("recipient", ""),
        "task_type": data.get("task_type", ""),
        "context": data.get("context") if isinstance(data.get("context"), dict) else {},
        "payload": data.get("payload") if isinstance(data.get("payload"), dict) else {},
        "status": data.get("status", "pending") or "pending",
        "error": data.get("error", "") or "",
    }
    if validate:
        Message.validate_envelope(normalized)
    return normalized
