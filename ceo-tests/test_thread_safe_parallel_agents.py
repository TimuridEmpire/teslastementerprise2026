"""
Thread-safe agents registered via ParallelAgentRuntime and stressed with parallel sends.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from typing import Any, Dict, List

from agent_backlog import AgentBacklog
from agents.advisor_agent import AdvisorAgent
from multithreaded_agent import ParallelAgentRuntime, send_messages_parallel
from thread_safe_agent import ThreadSafeAgentMixin
from message_bus import MessageBus


class RecordingAgent(ThreadSafeAgentMixin):
    """Minimal agent: records envelope ids processed under per-instance serialization."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.received_ids: List[str] = []

    def on_bus_envelope(self, envelope: Dict[str, Any]) -> Any:
        eid = str(envelope.get("id") or "")
        self.received_ids.append(eid)
        return {"agent": self.name, "echo_id": eid}


class TestParallelThreadSafeAgents(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        db = os.path.join(self._tmpdir.name, "backlog.db")
        jlog = os.path.join(self._tmpdir.name, "bus.jsonl")
        self.bus = MessageBus(backlog=AgentBacklog(db), json_log_path=jlog)

    def test_distinct_agents_run_concurrently_without_cross_talk(self) -> None:
        alpha = RecordingAgent("AlphaDept")
        beta = RecordingAgent("BetaDept")
        runtime = ParallelAgentRuntime(self.bus)
        runtime.register(alpha, beta)
        self.addCleanup(runtime.unregister_all)

        env_a = {
            "id": "m-a",
            "timestamp": "2026-01-01T00:00:00Z",
            "sender": "Orchestrator",
            "recipient": "AlphaDept",
            "task_type": "PING",
            "context": {},
            "payload": {},
            "status": "pending",
            "error": "",
        }
        env_b = {
            "id": "m-b",
            "timestamp": "2026-01-01T00:00:00Z",
            "sender": "Orchestrator",
            "recipient": "BetaDept",
            "task_type": "PING",
            "context": {},
            "payload": {},
            "status": "pending",
            "error": "",
        }
        results = send_messages_parallel(self.bus, [env_a, env_b])
        self.assertEqual(results[0], {"agent": "AlphaDept", "echo_id": "m-a"})
        self.assertEqual(results[1], {"agent": "BetaDept", "echo_id": "m-b"})
        self.assertEqual(alpha.received_ids, ["m-a"])
        self.assertEqual(beta.received_ids, ["m-b"])

    def test_same_agent_serializes_parallel_sends(self) -> None:
        agent = RecordingAgent("SoloDept")
        runtime = ParallelAgentRuntime(self.bus)
        runtime.register(agent)
        self.addCleanup(runtime.unregister_all)

        batch = [
            {
                "id": f"id-{i}",
                "timestamp": "2026-01-01T00:00:00Z",
                "sender": "X",
                "recipient": "SoloDept",
                "task_type": "PING",
                "context": {},
                "payload": {},
                "status": "pending",
                "error": "",
            }
            for i in range(20)
        ]
        send_messages_parallel(self.bus, batch, max_workers=8)
        self.assertEqual(len(agent.received_ids), 20)
        self.assertEqual(set(agent.received_ids), {f"id-{i}" for i in range(20)})

    def test_advisor_bus_path_is_thread_safe(self) -> None:
        advisor = AdvisorAgent(name="Advisor", core_strategy="software only")
        runtime = ParallelAgentRuntime(self.bus)
        runtime.register(advisor)
        self.addCleanup(runtime.unregister_all)

        envs = [
            {
                "id": f"rev-{i}",
                "timestamp": "2026-01-01T00:00:00Z",
                "sender": "CEO",
                "recipient": "Advisor",
                "task_type": "STRATEGY_REVIEW_REQUEST",
                "context": {},
                "payload": {"note": f"item {i}"},
                "status": "pending",
                "error": "",
            }
            for i in range(10)
        ]
        results = send_messages_parallel(self.bus, envs, max_workers=4)
        self.assertEqual(len(results), 10)
        for r in results:
            self.assertIsInstance(r, dict)
            self.assertEqual(r.get("task_type"), "STRATEGY_REVIEW_RESULT")


if __name__ == "__main__":
    unittest.main()
