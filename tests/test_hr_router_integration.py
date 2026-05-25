from __future__ import annotations

import importlib.util
from pathlib import Path


class FakeRouterClient:
    def __init__(self, envelope: dict | None):
        self.envelope = envelope
        self.acked = []
        self.nacked = []

    def fetch_next(self, recipient: str):
        assert recipient == "HR"
        envelope = self.envelope
        self.envelope = None
        return envelope

    def ack_message(self, message_id: str, recipient: str):
        self.acked.append((message_id, recipient))

    def nack_message(self, message_id: str, recipient: str, reason: str):
        self.nacked.append((message_id, recipient, reason))


def load_hr_agent_module():
    path = Path(__file__).resolve().parents[1] / "hr-agents" / "hr_agent.py"
    spec = importlib.util.spec_from_file_location("hr_agent_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_hr_envelope() -> dict:
    return {
        "id": "hr-msg-1",
        "timestamp": "2026-04-30T12:00:00Z",
        "sender": "CEO",
        "recipient": "HR",
        "task_type": "TALENT_REALLOCATION",
        "context": {},
        "payload": {"task": "Hire 2 engineering agents"},
        "status": "pending",
        "error": "",
    }


def test_process_one_hr_message_fetches_from_router_and_acks_after_success():
    hr_agent = load_hr_agent_module()
    client = FakeRouterClient(sample_hr_envelope())
    seen = []

    processed = hr_agent.process_one_hr_message(
        router_client=client,
        supervisor=lambda envelope: seen.append(envelope["id"]),
    )

    assert processed is True
    assert seen == ["hr-msg-1"]
    assert client.acked == [("hr-msg-1", "HR")]
    assert client.nacked == []


def test_process_one_hr_message_nacks_after_supervisor_failure():
    hr_agent = load_hr_agent_module()
    client = FakeRouterClient(sample_hr_envelope())

    def fail(_envelope):
        raise RuntimeError("boom")

    processed = hr_agent.process_one_hr_message(router_client=client, supervisor=fail)

    assert processed is True
    assert client.acked == []
    assert len(client.nacked) == 1
    assert client.nacked[0][0] == "hr-msg-1"
    assert client.nacked[0][1] == "HR"
    assert "boom" in client.nacked[0][2]
