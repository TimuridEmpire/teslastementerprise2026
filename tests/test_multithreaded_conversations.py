"""
Tests for multithreaded multi-topic conversations (``agents.multithreaded_agent``).
"""

from __future__ import annotations

import os
import tempfile
import threading
import unittest

from agent_backlog import AgentBacklog
import multithreaded_agent as mt
from message_bus import MessageBus


class TestMultithreadedConversations(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        db = os.path.join(self._tmpdir.name, "backlog.db")
        jlog = os.path.join(self._tmpdir.name, "bus.jsonl")
        self.bus = MessageBus(backlog=AgentBacklog(db), json_log_path=jlog)

    def test_parallel_send_result_order_matches_input(self) -> None:
        topics = ("alpha", "beta", "gamma")
        batch = [
            mt.make_topic_envelope(
                sender="S",
                topic=t,
                task_type=f"T_{i}",
                payload={"idx": i, "topic": t},
            )
            for i, t in enumerate(topics)
        ]
        # Handlers run synchronously in sender thread; return value shows up in results[i].
        for i, t in enumerate(topics):
            ch = mt.topic_channel_name(t)

            def _h(env: dict, expected_id: str = batch[i]["id"]) -> str:
                self.assertEqual(env.get("id"), expected_id)
                return expected_id

            self.bus.register(ch, _h)

        results = mt.send_messages_parallel(self.bus, batch)
        self.assertEqual(len(results), 3)
        for i in range(3):
            self.assertEqual(results[i], batch[i]["id"])

    def test_multiple_conversations_across_topics(self) -> None:
        """Several rounds × several topics: each topic receives all its messages."""
        topics = ("finance", "engineering", "marketing", "legal")
        rounds = 5
        lock = threading.Lock()
        received: dict[str, list[dict]] = {t: [] for t in topics}

        def handler(topic: str):
            def _on(env: dict) -> None:
                with lock:
                    received[topic].append(
                        {
                            "task_type": env.get("task_type"),
                            "round": env.get("payload", {}).get("round"),
                        }
                    )

            return _on

        coord = mt.MultiTopicAgentCoordinator(self.bus)
        for t in topics:
            coord.add_topic(t, handler(t))
        coord.start_all()

        channels = [mt.topic_channel_name(t) for t in topics]

        for r in range(rounds):
            batch = [
                mt.make_topic_envelope(
                    sender="Orchestrator",
                    topic=t,
                    task_type=f"ROUND_{r}",
                    payload={"round": r, "note": f"conversation {t} round {r}"},
                )
                for t in topics
            ]
            mt.send_messages_parallel(self.bus, batch)
            ok = mt.wait_for_mailboxes_drained(
                self.bus, channels, timeout_s=10.0, poll_s=0.01
            )
            self.assertTrue(ok, f"mailboxes should drain after round {r}")

        coord.stop_all()

        for t in topics:
            self.assertEqual(
                len(received[t]),
                rounds,
                f"topic {t} should get {rounds} messages, got {len(received[t])}",
            )
            rounds_seen = sorted(m["round"] for m in received[t])
            self.assertEqual(rounds_seen, list(range(rounds)))

    def test_mailboxes_empty_before_stop(self) -> None:
        topics = ("a", "b")
        received = {t: 0 for t in topics}
        lock = threading.Lock()

        def make_h(t: str):
            def _on(_env: dict) -> None:
                with lock:
                    received[t] += 1

            return _on

        coord = mt.MultiTopicAgentCoordinator(self.bus)
        for t in topics:
            coord.add_topic(t, make_h(t))
        coord.start_all()

        batch = [
            mt.make_topic_envelope(sender="X", topic="a", task_type="T1", payload={}),
            mt.make_topic_envelope(sender="X", topic="b", task_type="T2", payload={}),
        ]
        mt.send_messages_parallel(self.bus, batch)
        mt.wait_for_mailboxes_drained(
            self.bus,
            [mt.topic_channel_name(t) for t in topics],
            timeout_s=5.0,
        )
        self.assertEqual(self.bus.pending_count(mt.topic_channel_name("a")), 0)
        self.assertEqual(self.bus.pending_count(mt.topic_channel_name("b")), 0)
        self.assertEqual(received["a"], 1)
        self.assertEqual(received["b"], 1)
        coord.stop_all()


if __name__ == "__main__":
    unittest.main()
