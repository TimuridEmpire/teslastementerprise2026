"""
message_schema.py

Single Source of Truth for the Enterprise Agent Message Envelope.
This file defines the strict JSON schema required for all inter-agent 
communication over the Message Bus and stored in the Agent Backlog.

TODO: Refactor the rest of the repository (MessageBus, AgentBacklog, 
and individual agent classes) to instantiate and pass this `Message` 
dataclass instead of constructing raw, unvalidated Python dictionaries.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional


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

    # Used for strict validation of incoming dictionaries
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
        payload: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Factory method to generate a new message.
        Automatically handles UUID generation and ISO-8601 UTC timestamps.
        """
        return Message(
            id=f"msg-{uuid.uuid4().hex[:8]}", # Matches your req-001/msg-xxx format
            timestamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            sender=sender,
            recipient=recipient,
            task_type=task_type,
            context=context or {},
            payload=payload or {},
            status="pending",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Message object into a dictionary for JSON serialization."""
        return asdict(self)

    @staticmethod
    def validate_envelope(message: Dict[str, Any]) -> None:
        """
        Validates a raw dictionary against the strict enterprise schema.
        Raises ValueError if the payload is malformed or invalid.
        """
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