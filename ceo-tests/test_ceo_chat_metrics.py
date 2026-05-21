import unittest
from unittest.mock import patch

from agents.ceo_agent import CeoAgent


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class TestCeoChatAndMetrics(unittest.TestCase):
    def test_chat_endpoint_uses_ollama_chat_payload(self):
        ceo = CeoAgent(name="CEO")

        def fake_post(url, json, timeout):
            self.assertEqual(url, ceo.ollama_chat_url)
            self.assertEqual(json.get("model"), "mistral")
            self.assertEqual(json.get("stream"), False)
            self.assertIsInstance(json.get("messages"), list)
            self.assertEqual(timeout, 25)
            return _FakeResponse({"message": {"role": "assistant", "content": "hello"}})

        with patch("_ceo_agents_legacy.ceo_agent.requests.post", side_effect=fake_post):
            reply = ceo.chat_with_engine("hi")
        self.assertEqual(reply, "hello")
        self.assertEqual(len(ceo.chat_history), 2)

    def test_reasoning_loop_tracks_metrics_and_final_summary_time(self):
        ceo = CeoAgent(name="CEO")

        def fake_post(url, json, timeout):
            if url == ceo.ollama_generate_url:
                return _FakeResponse({"response": "Focus on enterprise upsell."})
            if url == ceo.ollama_chat_url:
                return _FakeResponse({"message": {"content": "Final CEO summary."}})
            raise AssertionError(f"Unexpected URL: {url}")

        with patch("_ceo_agents_legacy.ceo_agent.requests.post", side_effect=fake_post):
            result = ceo.execute_reasoning_loop(
                "Plan next quarter priorities",
                subordinate_agents=["PM", "Engineering", "Finance"],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["final_summary"], "Final CEO summary.")
        metrics = result["metrics"]
        self.assertEqual(metrics["success_count"], 1)
        self.assertEqual(metrics["failure_count"], 0)
        self.assertGreaterEqual(metrics["last_cycle_duration_ms"], 0)
        self.assertEqual(metrics["tasks_per_agent"]["PM"], 1)
        self.assertEqual(metrics["tasks_per_agent"]["Engineering"], 1)
        self.assertEqual(metrics["tasks_per_agent"]["Finance"], 1)


if __name__ == "__main__":
    unittest.main()
