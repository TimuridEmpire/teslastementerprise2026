"""
Shared enterprise-router transport for all department agents.

When ``ENTERPRISE_ROUTER_URL``, ``ENTERPRISE_AGENT_NAME``, and ``ENTERPRISE_AGENT_API_KEY``
are set, messages use the router HTTP API. Otherwise agents fall back to the in-process
``MessageBus`` (and optional legacy Mongo paths in Engineering).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from enterprise_router_client import EnterpriseRouterClient, router_configured
from message_bus import MessageBus, send_message
from message_schema import EnvelopeInput, Message, normalize_envelope

_default_bus: MessageBus | None = None

# Canonical router ids (must match scripts/bootstrap_router_agents.py)
AGENT_CEO = "CEO"
AGENT_PM = "PM"
AGENT_MARKETING = "Marketing"
AGENT_HR = "HR"
AGENT_ENGINEERING = "Engineering"
AGENT_SALES = "Sales"
AGENT_FINANCE = "Finance"
AGENT_ADVISOR = "Strategic Advisor"
AGENT_MANAGER = "MANAGER"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_envelope(
    *,
    sender: str,
    recipient: str,
    task_type: str,
    payload: Optional[dict[str, Any]] = None,
    context: Optional[dict[str, Any]] = None,
    status: str = "pending",
    error: str = "",
    message_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build and validate a canonical envelope dict."""
    return normalize_envelope(
        Message.create(
            sender=sender,
            recipient=recipient,
            task_type=task_type,
            context=context,
            payload=payload,
            status=status,
            error=error,
            message_id=message_id,
        )
    )


def _local_bus() -> MessageBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = MessageBus()
    return _default_bus


def client() -> EnterpriseRouterClient | None:
    return EnterpriseRouterClient.from_env()


def submit(
    envelope: EnvelopeInput,
    *,
    routing_hints: dict[str, Any] | None = None,
) -> str:
    """Submit an envelope; returns message id."""
    raw = normalize_envelope(envelope)
    if router_configured():
        c = client()
        assert c is not None
        return c.submit_message(raw, routing_hints=routing_hints)
    _local_bus().send(raw)
    return str(raw.get("id", ""))


def receive(recipient: str | None = None) -> dict[str, Any] | None:
    """Lease the next message for ``recipient`` (defaults to env agent name)."""
    if router_configured():
        c = client()
        assert c is not None
        who = (recipient or c.agent_name).strip()
        return c.fetch_next(who)
    who = (recipient or os.getenv("ENTERPRISE_AGENT_NAME") or "").strip()
    if not who:
        return None
    return _local_bus().receive(who)


def ack(message_id: str, recipient: str | None = None) -> None:
    if router_configured():
        c = client()
        assert c is not None
        c.ack(message_id, recipient)
        return
    # In-process mailbox: receive already removed the message.


def drain_mailbox(agent_name: str) -> list[dict[str, Any]]:
    """Fetch and ack all queued messages for an agent (router or local peek)."""
    from message_bus import get_messages_for

    return get_messages_for(agent_name)


def delegate(
    sender: str,
    recipient: str,
    task_type: str,
    payload: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    routing_hints: dict[str, Any] | None = None,
) -> str:
    """Build a standard envelope and submit it (sender must match env agent when using router)."""
    env = make_envelope(
        sender=sender,
        recipient=recipient,
        task_type=task_type,
        payload=payload,
        context=context,
    )
    return submit(env, routing_hints=routing_hints)
