"""
Thread-safe agent primitives for parallel message-bus delivery.

``MessageBus`` handlers run in the **caller's thread**. With ``send_messages_parallel``,
several handlers can run at once. Each agent instance keeps a reentrant lock so that
only one unit of work touches that agent at a time, while *different* agents still run
concurrently.

Use ``handle_bus_message`` (or ``as_bus_handler()`` for ``bus.register``) as the single
entry point from the bus. Public methods that may be called directly from application
code should also use ``self._agent_lock`` so direct and bus-driven use stay consistent.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Protocol


class ThreadSafeAgentMixin:
    """
    Adds ``_agent_lock`` (reentrant) and ``handle_bus_message`` / ``as_bus_handler``.

    Subclasses must implement ``on_bus_envelope(envelope)`` for bus-routed work.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._agent_lock = threading.RLock()
        super().__init__(*args, **kwargs)

    def on_bus_envelope(self, envelope: Dict[str, Any]) -> Any:
        raise NotImplementedError

    def handle_bus_message(self, envelope: Dict[str, Any]) -> Any:
        with self._agent_lock:
            return self.on_bus_envelope(envelope)

    def as_bus_handler(self) -> Callable[[Dict[str, Any]], Any]:
        """Return a callable suitable for ``MessageBus.register(self.name, ...)``."""
        return self.handle_bus_message


class SupportsBusRegistration(Protocol):
    """Structural type for :class:`ParallelAgentRuntime`."""

    name: str

    def as_bus_handler(self) -> Callable[[Dict[str, Any]], Any]: ...
