import unittest
from unittest.mock import patch

import requests

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

    def test_talk_to_engine_retries_once_after_timeout_then_succeeds(self):
        """Regression test: on a memory-constrained machine, Ollama evicts and
        reloads models between calls, so this call can time out even though
        the model finishes loading server-side moments later. Reproduced
        live: the generate call timed out while the very next chat call
        succeeded immediately. Retrying once should pick up the now-warm
        model instead of reporting a spurious error."""
        ceo = CeoAgent(name="CEO")
        calls = []

        def fake_post(url, json, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise requests.Timeout("Read timed out. (read timeout=30)")
            return _FakeResponse({"response": "Focus on enterprise upsell."})

        with patch("_ceo_agents_legacy.ceo_agent.requests.post", side_effect=fake_post):
            with patch("_ceo_agents_legacy.ceo_agent.time.sleep") as sleep_mock:
                result = ceo.talk_to_engine("What should we prioritize?")

        self.assertEqual(result, "Focus on enterprise upsell.")
        self.assertEqual(len(calls), 2)
        sleep_mock.assert_called_once()

    def test_talk_to_engine_reports_error_after_both_attempts_fail(self):
        ceo = CeoAgent(name="CEO")
        calls = []

        def fake_post(url, json, timeout):
            calls.append(url)
            raise requests.Timeout("Read timed out. (read timeout=30)")

        with patch("_ceo_agents_legacy.ceo_agent.requests.post", side_effect=fake_post):
            with patch("_ceo_agents_legacy.ceo_agent.time.sleep"):
                result = ceo.talk_to_engine("What should we prioritize?")

        self.assertIn("Strategic Link Error", result)
        self.assertEqual(len(calls), 2)

    def test_chat_with_engine_retries_once_after_timeout_then_succeeds(self):
        """Same model-swap contention as _talk_to_engine_unlocked, but for the
        chat endpoint — reproduced live: the chat call timed out immediately
        after a successful generate call to the same model."""
        ceo = CeoAgent(name="CEO")
        calls = []

        def fake_post(url, json, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise requests.Timeout("Read timed out. (read timeout=25)")
            return _FakeResponse({"message": {"content": "hello"}})

        with patch("_ceo_agents_legacy.ceo_agent.requests.post", side_effect=fake_post):
            with patch("_ceo_agents_legacy.ceo_agent.time.sleep") as sleep_mock:
                reply = ceo.chat_with_engine("hi")

        self.assertEqual(reply, "hello")
        self.assertEqual(len(calls), 2)
        sleep_mock.assert_called_once()
        # Only one user/assistant pair recorded, not one per attempt.
        self.assertEqual(len(ceo.chat_history), 2)


if __name__ == "__main__":
    unittest.main()
