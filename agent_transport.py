"""
Shared enterprise-router transport for all department agents.

Runtime agent-to-agent messages must use the Enterprise Router HTTP API. The in-process
``MessageBus`` is available only when an explicit offline/demo flag is set.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from enterprise_router_client import (
    EnterpriseRouterClient,
    router_agent_name,
    router_configured,
    router_missing_config,
)
from message_bus import MessageBus
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


def _env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def local_fallback_enabled() -> bool:
    return _env_flag_enabled("ENTERPRISE_ROUTER_OFFLINE_DEMO")


def require_router_configured(agent_name: str | None = None) -> None:
    if router_configured() or not router_missing_config(agent_name):
        return
    if local_fallback_enabled():
        return
    missing = router_missing_config(agent_name)
    detail = ", ".join(missing) if missing else "complete router credentials"
    raise RuntimeError(
        "Enterprise Router is required for runtime agent-to-agent communication. "
        f"Missing {detail}. Set ENTERPRISE_ROUTER_OFFLINE_DEMO=1 only for tests "
        "or offline demos that intentionally use the local MessageBus."
    )


def client(agent_name: str | None = None) -> EnterpriseRouterClient | None:
    return EnterpriseRouterClient.from_env(agent_name=agent_name)


def submit(
    envelope: EnvelopeInput,
    *,
    routing_hints: dict[str, Any] | None = None,
) -> str:
    """Submit an envelope; returns message id."""
    raw = normalize_envelope(envelope)
    sender = str(raw.get("sender") or "")
    require_router_configured(sender)
    if not local_fallback_enabled():
        c = client(sender)
        assert c is not None
        return c.submit_message(raw, routing_hints=routing_hints)
    _local_bus().send(raw)
    return str(raw.get("id", ""))


send = submit


def receive(recipient: str | None = None) -> dict[str, Any] | None:
    """Lease the next message for ``recipient`` (defaults to env agent name)."""
    who = (recipient or router_agent_name() or "").strip()
    require_router_configured(who)
    if not local_fallback_enabled():
        c = client(who)
        assert c is not None
        return c.fetch_next(who)
    if not who:
        return None
    return _local_bus().receive(who)


fetch = receive


def ack(message_id: str, recipient: str | None = None) -> None:
    who = (recipient or router_agent_name() or "").strip()
    require_router_configured(who)
    if not local_fallback_enabled():
        c = client(who)
        assert c is not None
        c.ack(message_id, who)
        return
    # In-process mailbox: receive already removed the message.


def nack(message_id: str, recipient: str | None = None, *, reason: str) -> None:
    who = (recipient or router_agent_name() or "").strip()
    require_router_configured(who)
    if not local_fallback_enabled():
        c = client(who)
        assert c is not None
        c.nack(message_id, reason, who)
        return
    # In-process mailbox has no lease state to reject.


def drain_mailbox(agent_name: str) -> list[dict[str, Any]]:
    """Fetch and ack all queued messages for an agent (router or explicit local demo)."""
    require_router_configured(agent_name)
    if not local_fallback_enabled():
        c = client(agent_name)
        assert c is not None
        drained: list[dict[str, Any]] = []
        while True:
            envelope = c.fetch_next(agent_name)
            if not envelope:
                break
            drained.append(envelope)
            message_id = envelope.get("id")
            if message_id:
                c.ack(str(message_id), agent_name)
        return drained

    drained = []
    while True:
        envelope = _local_bus().receive(agent_name)
        if not envelope:
            break
        drained.append(envelope)
    return drained


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
