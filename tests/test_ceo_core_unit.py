import unittest
from unittest import mock
import importlib

from agents.ceo_agent import CeoAgent


class TestCeoCoreUnit(unittest.TestCase):
    def test_ping_envelope_acknowledged(self):
        ceo = CeoAgent(name="CEO")

        out = ceo.on_bus_envelope({"task_type": "CEO_PING", "payload": {}})

        self.assertEqual(out["ok"], True)
        self.assertEqual(out["agent"], "CEO")
        self.assertEqual(out["task_type"], "CEO_PING")

    def test_environment_signal_envelope_updates_state(self):
        ceo = CeoAgent(name="CEO")
        self.assertFalse(ceo.children_nearby_detected)

        out = ceo.on_bus_envelope(
            {
                "task_type": "CEO_ENVIRONMENT_SIGNAL",
                "payload": {"children_nearby": True},
            }
        )

        self.assertEqual(out["ok"], True)
        self.assertTrue(out["children_nearby_detected"])
        self.assertTrue(ceo.children_nearby_detected)

    def test_reasoning_loop_reroutes_when_children_nearby(self):
        ceo = CeoAgent(name="CEO")

        out = ceo.execute_reasoning_loop(
            "Plan next quarter",
            subordinate_agents=["PM Agent"],
            context={"children_nearby": True},
        )

        self.assertFalse(out["ok"])
        self.assertIn("reroute", out)
        self.assertEqual(out["reroute"]["reason"], "children_nearby_detected")
        self.assertEqual(out["metrics"]["failure_count"], 1)
        self.assertEqual(out["metrics"]["success_count"], 0)

    def test_reasoning_loop_audio_policy_violation_fails_cleanly(self):
        ceo = CeoAgent(name="CEO")

        out = ceo.execute_reasoning_loop(
            "Summarize roadmap",
            subordinate_agents=["PM Agent"],
            context={"audio_policy": {"processed_locally": False, "stored_externally": False}},
        )

        self.assertFalse(out["ok"])
        self.assertIn("Audio privacy boundary violation", out["final_summary"])
        self.assertEqual(out["metrics"]["failure_count"], 1)
        self.assertEqual(out["metrics"]["success_count"], 0)

    def test_gather_only_updates_metrics_per_agent(self):
        ceo = CeoAgent(name="CEO")
        departments = ["PM Agent", "Engineering Agent", "PM Agent"]

        out = ceo.on_bus_envelope(
            {
                "task_type": "CEO_GATHER_ONLY",
                "payload": {"departments": departments},
            }
        )

        self.assertEqual(len(out), 3)
        metrics = ceo.get_metrics()
        self.assertEqual(metrics["tasks_per_agent"]["PM Agent"], 2)
        self.assertEqual(metrics["tasks_per_agent"]["Engineering Agent"], 1)

    def test_writing_strategy_artifact_emits_router_event(self):
        ceo = CeoAgent(name="CEO")
        fake_record = {
            "artifact_id": "art-1234abcd",
            "artifact_type": "strategy",
            "title": "CEO executive summary",
            "filename": "artifact.md",
            "created_at": "2026-05-26T00:00:00Z",
            "source_task_type": "CEO_REASONING_LOOP",
            "metadata": {"source": "test"},
        }

        ceo_module = importlib.import_module(ceo.__class__.__module__)
        with mock.patch.object(ceo_module, "write_agent_artifact", return_value=fake_record) as writer:
            with mock.patch.object(ceo, "send_router_envelope", return_value="msg-1") as sender:
                out = ceo._write_strategy_artifact_unlocked(
                    title="CEO executive summary",
                    body="summary",
                    artifact_type="strategy",
                    metadata={"source": "test"},
                    source_task_type="CEO_REASONING_LOOP",
                )

        self.assertEqual(out, fake_record)
        writer.assert_called_once()
        sender.assert_called_once()
        kwargs = sender.call_args.kwargs
        self.assertEqual(kwargs["recipient"], "MANAGER")
        self.assertEqual(kwargs["task_type"], "AGENT_ARTIFACT_READY")
        self.assertEqual(kwargs["payload"]["artifact_id"], "art-1234abcd")

    def test_oversee_company_writes_exact_final_strategy_to_artifact_body(self):
        ceo = CeoAgent(name="CEO")
        expected_strategy = "Focus Q3 on enterprise retention with high-touch onboarding."

        with mock.patch.object(ceo, "_make_strategic_decision_unlocked", return_value=expected_strategy):
            with mock.patch.object(ceo, "_write_strategy_artifact_unlocked", return_value={"artifact_id": "art-1"}) as writer:
                out = ceo.oversee_company(["PM Agent", "Marketing Agent"])

        self.assertEqual(out, expected_strategy)
        writer.assert_called_once()
        self.assertEqual(writer.call_args.kwargs["body"], expected_strategy)


if __name__ == "__main__":
    unittest.main()
