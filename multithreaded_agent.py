"""
Concurrent multi-topic agent coordination on top of the thread-safe MessageBus.

- Each topic maps to a dedicated bus recipient name: ``topic:<name>``.
- ``TopicListener`` runs in its own thread and pulls messages for that channel via
  ``receive``, so several topics are processed in parallel without blocking each other.
- ``send_messages_parallel`` dispatches multiple envelopes concurrently (e.g. one
  outbound conversation per topic at the same time).
- ``ParallelAgentRuntime`` registers agents that use :class:`~agents.thread_safe_agent.ThreadSafeAgentMixin`
  so each agent's ``handle_bus_message`` runs under that agent's lock; different agents
  still execute in parallel when sends are parallelized.

Handlers are not registered for topic channels so messages are queued; listeners
consume from mailboxes in their own threads.
"""

from __future__ import annotations

import datetime
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Iterable, List, Optional

from message_bus import MessageBus

from thread_safe_agent import SupportsBusRegistration

TopicHandler = Callable[[Dict[str, Any]], None]


def wait_for_mailboxes_drained(
    bus: MessageBus,
    channel_names: Iterable[str],
    *,
    timeout_s: float = 5.0,
    poll_s: float = 0.02,
) -> bool:
    """
    Block until every listed channel has ``pending_count`` 0, or ``timeout_s`` elapses.
    Use after parallel sends to topic listeners so you do not shut down while mailboxes
    still hold messages — ``bus.send`` can return before ``TopicListener`` threads dequeue.
    """
    channels = list(channel_names)
    if not channels:
        return True
    deadline = time.time() + timeout_s
    poll = max(0.001, float(poll_s))
    while time.time() < deadline:
        if all(bus.pending_count(ch) == 0 for ch in channels):
            return True
        time.sleep(poll)
    return False


def topic_channel_name(topic: str) -> str:
    """Bus recipient name for a topic channel (stable prefix)."""
    t = (topic or "").strip()
    if not t:
        raise ValueError("topic must be non-empty")
    return f"topic:{t}"


def make_topic_envelope(
    *,
    sender: str,
    topic: str,
    task_type: str,
    payload: Dict[str, Any],
    recipient: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a standard envelope routed to ``topic:<topic>`` with topic in context."""
    ch = topic_channel_name(topic)
    ctx = dict(context or {})
    ctx.setdefault("topic", topic)
    return {
        "id": f"msg-{uuid.uuid4().hex[:10]}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "sender": sender,
        "recipient": recipient or ch,
        "task_type": task_type,
        "context": ctx,
        "payload": payload,
        "status": "pending",
        "error": "",
    }


def send_messages_parallel(
    bus: MessageBus,
    messages: Iterable[Dict[str, Any]],
    *,
    max_workers: Optional[int] = None,
) -> List[Any]:
    """
    Send several envelopes concurrently. Each call runs ``bus.send`` in a worker thread.
    Return values are ordered to match ``messages`` (same index as input), even though
    sends may complete in a different order.
    """
    msgs = list(messages)
    if not msgs:
        return []
    workers = max_workers or min(32, len(msgs))
    results: List[Optional[Any]] = [None] * len(msgs)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(bus.send, m): i for i, m in enumerate(msgs)}
        for fut in as_completed(futures):
            idx = futures[fut]
            results[idx] = fut.result()
    return results  # type: ignore[return-value]


class TopicListener(threading.Thread):
    """
    Background consumer for one topic channel: repeatedly ``receive``s until stopped.
    """

    def __init__(
        self,
        bus: MessageBus,
        topic: str,
        on_message: TopicHandler,
        *,
        poll_interval_s: float = 0.05,
        name: Optional[str] = None,
    ):
        super().__init__(name=name or f"TopicListener[{topic}]", daemon=True)
        self._bus = bus
        self._topic = topic
        self._channel = topic_channel_name(topic)
        self._on_message = on_message
        self._poll = max(0.01, float(poll_interval_s))
        # Must not shadow threading.Thread._stop (method used by join()).
        self._halt = threading.Event()

    @property
    def channel(self) -> str:
        return self._channel

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        while not self._halt.is_set():
            msg = self._bus.receive(self._channel)
            if msg is not None:
                self._on_message(msg)
            else:
                self._halt.wait(self._poll)


class ParallelAgentRuntime:
    """
    Registers one or more thread-safe agents on a :class:`MessageBus` for push delivery.

    ``MessageBus.send`` invokes the recipient's handler in the **sender's** thread.
    With :func:`send_messages_parallel`, different recipients run concurrently; each
    agent's reentrant lock ensures a single in-flight handler for that instance so
    internal state and workflows stay consistent.
    """

    def __init__(self, bus: MessageBus):
        self._bus = bus
        self._agents: List[SupportsBusRegistration] = []

    def register(self, *agents: SupportsBusRegistration) -> None:
        for agent in agents:
            self._bus.register(agent.name, agent.as_bus_handler())
            self._agents.append(agent)

    def unregister_all(self) -> None:
        for agent in self._agents:
            self._bus.register(agent.name, None)
        self._agents.clear()


class MultiTopicAgentCoordinator:
    """
    Owns one ``TopicListener`` thread per registered topic; start/stop as a group.
    """

    def __init__(self, bus: MessageBus):
        self._bus = bus
        self._listeners: List[TopicListener] = []

    def add_topic(self, topic: str, on_message: TopicHandler) -> TopicListener:
        listener = TopicListener(self._bus, topic, on_message)
        self._listeners.append(listener)
        return listener

    def start_all(self) -> None:
        for t in self._listeners:
            if not t.is_alive():
                t.start()

    def stop_all(self, join_timeout_s: float = 5.0) -> None:
        for t in self._listeners:
            t.stop()
        for t in self._listeners:
            t.join(timeout=join_timeout_s)


def _demo() -> None:
    """Run a small in-process demo: three topics, parallel sends, concurrent listeners."""
    # Uses the same enterprise backlog + JSONL as other agents (see enterprise_paths).
    bus = MessageBus()

    lock = threading.Lock()
    received: Dict[str, List[str]] = {}

    def make_handler(topic: str) -> TopicHandler:
        def _on(envelope: Dict[str, Any]) -> None:
            summary = envelope.get("payload", {}).get("summary", "")
            line = f"{envelope.get('sender')} -> {topic}: {summary}"
            with lock:
                received.setdefault(topic, []).append(line)
            print(f"[{topic}] {line}")

        return _on

    coord = MultiTopicAgentCoordinator(bus)
    for t in ("finance", "engineering", "marketing"):
        coord.add_topic(t, make_handler(t))
    coord.start_all()

    batch = [
        make_topic_envelope(
            sender="CEO",
            topic="finance",
            task_type="Q2_BUDGET",
            payload={"summary": "Review runway and OpEx"},
        ),
        make_topic_envelope(
            sender="CEO",
            topic="engineering",
            task_type="PLATFORM_ROADMAP",
            payload={"summary": "Prioritize API reliability"},
        ),
        make_topic_envelope(
            sender="CEO",
            topic="marketing",
            task_type="CAMPAIGN_PLAN",
            payload={"summary": "Launch narrative for SMB"},
        ),
    ]

    send_messages_parallel(bus, batch)
    chs = [topic_channel_name(t) for t in ("finance", "engineering", "marketing")]
    wait_for_mailboxes_drained(bus, chs, timeout_s=5.0)
    coord.stop_all()

    print("--- demo summary ---")
    for topic, lines in sorted(received.items()):
        print(f"  {topic}: {len(lines)} message(s)")


if __name__ == "__main__":
    _demo()
