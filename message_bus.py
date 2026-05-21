"""
Shared in-memory message bus: routes standardized agent envelopes to recipients,
persists each message to the same store as agent_backlog plus a JSONL audit file.
Agents only need the envelope dict; senders and recipients are identified by name.
"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict, deque
from typing import Any, Callable, DefaultDict, Deque, Dict, List, Optional, TYPE_CHECKING

from agent_backlog import AgentBacklog
from agent_logger import get_agent_logger, log_inter_agent_message
from enterprise_paths import message_bus_jsonl_path

if TYPE_CHECKING:
    from ceo_distribution_tokens import CeoDistributionTokenRegistry

Handler = Callable[[Dict[str, Any]], Any]


def normalize_envelope(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Fill missing keys so backlog / JSON logs stay aligned with agent_backlog."""
    return {
        "id": raw.get("id", ""),
        "timestamp": raw.get("timestamp", ""),
        "sender": raw.get("sender", ""),
        "recipient": raw.get("recipient", ""),
        "task_type": raw.get("task_type", ""),
        "context": raw.get("context") if isinstance(raw.get("context"), dict) else {},
        "payload": raw.get("payload") if isinstance(raw.get("payload"), dict) else {},
        "status": raw.get("status", ""),
        "error": raw.get("error", "") or "",
    }


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
    """

    def __init__(
        self,
        backlog: Optional[AgentBacklog] = None,
        json_log_path: Optional[str] = None,
        distribution_tokens: Optional["CeoDistributionTokenRegistry"] = None,
        enforce_distribution_tokens: bool = False,
    ):
        self._backlog = backlog or AgentBacklog()
        self._json_log_path = (
            json_log_path if json_log_path is not None else message_bus_jsonl_path()
        )
        self._distribution_tokens = distribution_tokens
        self._enforce_distribution_tokens = bool(
            enforce_distribution_tokens and distribution_tokens is not None
        )
        self._lock = threading.Lock()
        self._persist_lock = threading.Lock()
        self._handlers: Dict[str, Handler] = {}
        self._mailboxes: DefaultDict[str, Deque[Dict[str, Any]]] = defaultdict(deque)
        self._logger = get_agent_logger("MessageBus")

    @property
    def json_log_path(self) -> str:
        return self._json_log_path

    def register(self, agent_name: str, handler: Optional[Handler] = None) -> None:
        """Register a synchronous handler for direct delivery. Pass None to clear."""
        with self._lock:
            if handler is None:
                self._handlers.pop(agent_name, None)
            else:
                self._handlers[agent_name] = handler

    def _persist(self, envelope: Dict[str, Any]) -> None:
        with self._persist_lock:
            self._backlog.record_interaction(envelope)
            _append_jsonl(self._json_log_path, envelope)

    def send(self, message: Dict[str, Any]) -> Optional[Any]:
        """
        Route a message: normalize, persist (SQLite backlog + JSONL), log, then deliver.
        Returns handler return value if a handler ran, else None (message queued in mailbox).

        When ``enforce_distribution_tokens`` is on and a registry is configured, envelopes
        that name a **registered** scenario in ``context.distribution_scenario`` or
        ``context.prompt_scenario`` consume tokens from the **sender** before persistence.
        """
        # Import locally to avoid circular imports if ceo_distribution_tokens ever imports the bus.
        from ceo_distribution_tokens import (
            DistributionTokenError,
            resolve_distribution_scenario,
        )

        envelope = normalize_envelope(message)

        if self._enforce_distribution_tokens and self._distribution_tokens is not None:
            scenario = resolve_distribution_scenario(envelope)
            if scenario and self._distribution_tokens.is_registered(scenario):
                sender = (envelope.get("sender") or "").strip()
                if not sender:
                    raise DistributionTokenError(
                        "Token-gated send requires a non-empty sender.",
                        scenario=scenario,
                        sender=sender,
                        balance=0,
                        cost=self._distribution_tokens.cost_for(scenario),
                    )
                cost = self._distribution_tokens.cost_for(scenario)
                if not self._distribution_tokens.try_consume(sender, scenario, cost):
                    bal = self._distribution_tokens.balance(sender, scenario)
                    raise DistributionTokenError(
                        f"Insufficient distribution tokens for scenario {scenario!r}: "
                        f"holder {sender!r} has {bal}, need {cost}.",
                        scenario=scenario,
                        sender=sender,
                        balance=bal,
                        cost=cost,
                    )

        self._persist(envelope)
        log_inter_agent_message(self._logger, envelope, direction="ROUTING")

        recipient = envelope.get("recipient") or ""
        with self._lock:
            handler = self._handlers.get(recipient)

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

    def receive(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Pop one message for this agent from the mailbox (FIFO). Returns None if empty.
        """
        with self._lock:
            q = self._mailboxes.get(agent_name)
            if not q:
                return None
            return q.popleft()

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
