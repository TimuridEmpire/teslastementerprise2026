import unittest

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


if __name__ == "__main__":
    unittest.main()
