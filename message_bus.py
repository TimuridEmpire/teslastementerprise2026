"""
bus/message_bus.py — Upgraded Enterprise Swarm Edition

Routes standardized agent envelopes to recipients, persists each message to the 
AgentBacklog and a JSONL audit file, enforces distribution tokens, and tracks global FinOps.

Features added for Agentic AI Scale:
- Broadcast routing (recipient="broadcast")
- Global session telemetry (tokens/cost tracking)
- Async-compatible wrappers for high-concurrency event loops
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from collections import defaultdict, deque
from typing import Any, Callable, DefaultDict, Deque, Dict, List, Optional, TYPE_CHECKING

from agent_backlog import AgentBacklog
from agent_logger import get_agent_logger, log_inter_agent_message
from enterprise_paths import message_bus_jsonl_path
from message_schema import EnvelopeInput, Message, normalize_envelope

if TYPE_CHECKING:
    from ceo_distribution_tokens import CeoDistributionTokenRegistry

Handler = Callable[[Dict[str, Any]], Any]


def _append_jsonl(path: str, record: Dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False) + "\n"
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


class MessageBus:
    """
    Thread-safe router: send(envelope) persists, logs, then delivers to a registered
    handler or holds the message in a per-recipient mailbox for pull-based agents.
    Supports async AI scaling and broadcast messaging.
    """

    def __init__(
        self,
        backlog: Optional[AgentBacklog] = None,
        json_log_path: Optional[str] = None,
        distribution_tokens: Optional["CeoDistributionTokenRegistry"] = None,
        enforce_distribution_tokens: bool = False,
    ):
        # Persistence & Gating
        self._backlog = backlog or AgentBacklog()
        self._json_log_path = (
            json_log_path if json_log_path is not None else message_bus_jsonl_path()
        )
        self._distribution_tokens = distribution_tokens
        self._enforce_distribution_tokens = bool(
            enforce_distribution_tokens and distribution_tokens is not None
        )
        
        # Thread Safety & State
        self._lock = threading.Lock()
        self._persist_lock = threading.Lock()
        self._handlers: Dict[str, Handler] = {}
        self._mailboxes: DefaultDict[str, Deque[Dict[str, Any]]] = defaultdict(deque)
        self._known_agents: set[str] = set()  # Track all known agents for broadcasting
        self._logger = get_agent_logger("MessageBus")

        # Global Session Telemetry
        self._stats_lock = threading.Lock()
        self._session_stats = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "messages_sent": 0,
            "broadcasts_sent": 0
        }

    @property
    def json_log_path(self) -> str:
        return self._json_log_path

    def register(self, agent_name: str, handler: Optional[Handler] = None) -> None:
        """Register a synchronous handler for direct delivery. Pass None to clear."""
        with self._lock:
            self._known_agents.add(agent_name)
            if handler is None:
                self._handlers.pop(agent_name, None)
            else:
                self._handlers[agent_name] = handler
        self._logger.info("[BUS] Registered agent: %s", agent_name)

    def get_session_stats(self) -> dict:
        """Retrieve global token and cost metrics."""
        with self._stats_lock:
            return dict(self._session_stats)

    def _update_telemetry(self, envelope: Dict[str, Any], is_broadcast: bool = False) -> None:
        """Passively aggregate global token usage across the enterprise swarm."""
        tu = envelope.get("token_usage", {})
        with self._stats_lock:
            self._session_stats["messages_sent"] += 1
            if is_broadcast:
                self._session_stats["broadcasts_sent"] += 1
            if tu:
                self._session_stats["total_input_tokens"] += tu.get("input_tokens", 0)
                self._session_stats["total_output_tokens"] += tu.get("output_tokens", 0)
                self._session_stats["total_tokens"] += tu.get("total_tokens", 0)
                self._session_stats["total_cost_usd"] += tu.get("cost_usd", 0.0)

    def _persist(self, envelope: Dict[str, Any]) -> None:
        with self._persist_lock:
            self._backlog.record_interaction(envelope)
            _append_jsonl(self._json_log_path, envelope)

    def send(self, message: EnvelopeInput) -> Optional[Any]:
        """
        Route a message: normalize, check tokens, persist, track telemetry, then deliver.
        Supports recipient="broadcast" for swarm-wide alerts.
        """
        # Import locally to avoid circular imports
        from ceo_distribution_tokens import (
            DistributionTokenError,
            resolve_distribution_scenario,
        )

        envelope = normalize_envelope(message)
        recipient = envelope.get("recipient", "")
        is_broadcast = (recipient.lower() == "broadcast")

        # 1. Enterprise Token Gating (Active Defense)
        if self._enforce_distribution_tokens and self._distribution_tokens is not None:
            scenario = resolve_distribution_scenario(envelope)
            if scenario and self._distribution_tokens.is_registered(scenario):
                sender = (envelope.get("sender") or "").strip()
                cost = self._distribution_tokens.cost_for(scenario)
                
                # Multiply cost by number of agents if broadcasting
                if is_broadcast:
                    cost *= max(1, len(self._known_agents))

                if not sender:
                    raise DistributionTokenError(
                        "Token-gated send requires a non-empty sender.",
                        scenario=scenario, sender=sender, balance=0, cost=cost
                    )
                if not self._distribution_tokens.try_consume(sender, scenario, cost):
                    bal = self._distribution_tokens.balance(sender, scenario)
                    raise DistributionTokenError(
                        f"Insufficient distribution tokens for scenario {scenario!r}: "
                        f"holder {sender!r} has {bal}, need {cost}.",
                        scenario=scenario, sender=sender, balance=bal, cost=cost
                    )

        # 2. Persistence & Telemetry (Passive Tracking)
        self._persist(envelope)
        self._update_telemetry(envelope, is_broadcast)
        log_inter_agent_message(self._logger, envelope, direction="ROUTING")

        # 3. Delivery Logic
        if is_broadcast:
            return self._handle_broadcast(envelope)
        else:
            return self._handle_point_to_point(envelope, recipient)

    def _handle_point_to_point(self, envelope: Dict[str, Any], recipient: str) -> Optional[Any]:
        with self._lock:
            handler = self._handlers.get(recipient)
            self._known_agents.add(recipient)  # Implicit discovery

        if handler:
            try:
                result = handler(envelope)
                self._logger.info(
                    "[DELIVERED] %s -> %s | id=%s | task=%s",
                    envelope.get("sender"),
                    recipient,
                    envelope.get("id"),
                    envelope.get("task_type"),
                )
                return result
            except Exception as exc:
                self._logger.exception("Handler for %s failed: %s", recipient, exc)
                raise

        with self._lock:
            self._mailboxes[recipient].append(envelope)
        self._logger.info(
            "No handler for [%s]; message id=%s queued in mailbox",
            recipient,
            envelope.get("id"),
        )
        return None

    def _handle_broadcast(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver to all known agents. Returns a dict of responses from sync handlers."""
        results = {}
        with self._lock:
            targets = list(self._known_agents)
            handlers_snapshot = dict(self._handlers)

        for agent in targets:
            agent_envelope = dict(envelope, recipient=agent, original_recipient="broadcast")
            if agent in handlers_snapshot:
                try:
                    results[agent] = handlers_snapshot[agent](agent_envelope)
                except Exception as exc:
                    self._logger.error("Broadcast handler failed for %s: %s", agent, exc)
            else:
                with self._lock:
                    self._mailboxes[agent].append(agent_envelope)
                    
        self._logger.info(
            "[BROADCAST DELIVERED] %s -> %d agents | id=%s | task=%s",
            envelope.get("sender"),
            len(targets),
            envelope.get("id"),
            envelope.get("task_type"),
        )
        return results

    def receive(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Pop one message for this agent from the mailbox (FIFO). Returns None if empty."""
        with self._lock:
            q = self._mailboxes.get(agent_name)
            if not q:
                return None
            return q.popleft()

    # --- Async Compatibility Wrappers ---

    async def async_send(self, message: Dict[str, Any]) -> Optional[Any]:
        """Non-blocking send for async AI agents yielding to the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.send, message)

    async def async_receive(self, agent_name: str, timeout: float = 30.0, poll_interval: float = 0.1) -> Optional[Dict[str, Any]]:
        """Async pull with timeout (emulates async Queues safely on top of sync threading)."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        
        while (loop.time() - start_time) < timeout:
            msg = self.receive(agent_name)
            if msg:
                return msg
            await asyncio.sleep(poll_interval)
            
        return None

    def peek_mailbox(self, agent_name: str) -> List[Dict[str, Any]]:
        """Snapshot of queued messages for an agent (does not remove)."""
        with self._lock:
            q = self._mailboxes.get(agent_name)
            if not q:
                return []
            return list(q)

    def pending_count(self, agent_name: str) -> int:
        with self._lock:
            return len(self._mailboxes.get(agent_name, ()))


# ---------------------------------------------------------------------------
# Cross-service routing via Enterprise Router (when env is configured)
# ---------------------------------------------------------------------------

_default_bus: MessageBus | None = None


def _get_default_bus() -> MessageBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = MessageBus()
    return _default_bus


def send_message(message: Message | dict[str, Any]) -> str | None:
    """
    Route a message: enterprise HTTP router when configured, else in-process bus.
    Returns message id from the router, or the handler result from the local bus.
    """
    from agent_transport import local_fallback_enabled
    from enterprise_router_client import EnterpriseRouterClient, router_configured

    envelope = normalize_envelope(message)

    if router_configured():
        client = EnterpriseRouterClient.from_env()
        assert client is not None
        return client.submit_message(envelope)

    if not local_fallback_enabled():
        raise RuntimeError(
            "Local MessageBus send_message is available only for explicit offline demos/tests. "
            "Set ENTERPRISE_ROUTER_OFFLINE_DEMO=1 or use agent_transport.submit()."
        )
    _get_default_bus().send(envelope)
    return envelope.get("id")


def get_messages_for(agent_name: str) -> list[dict[str, Any]]:
    """
    Drain messages for an agent: peek+fetch via router, or snapshot local mailbox.
    """
    from agent_transport import local_fallback_enabled
    from enterprise_router_client import EnterpriseRouterClient, router_configured

    if router_configured():
        client = EnterpriseRouterClient.from_env()
        assert client is not None
        drained: list[dict[str, Any]] = []
        while True:
            env = client.fetch_next(agent_name)
            if not env:
                break
            drained.append(env)
            mid = env.get("id")
            if mid:
                try:
                    client.ack(str(mid), agent_name)
                except Exception:
                    pass
        return drained

    if not local_fallback_enabled():
        raise RuntimeError(
            "Local MessageBus mailboxes are available only for explicit offline demos/tests. "
            "Set ENTERPRISE_ROUTER_OFFLINE_DEMO=1 or use agent_transport.receive()."
        )
    return _get_default_bus().peek_mailbox(agent_name)