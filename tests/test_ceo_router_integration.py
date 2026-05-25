from __future__ import annotations

from agents.ceo_agent import CeoAgent
from ceo_distribution_tokens import CeoDistributionTokenRegistry


class FakeRouterClient:
    def __init__(self, envelope: dict | None = None):
        self.envelope = envelope
        self.acked = []
        self.nacked = []
        self.submitted = []

    def fetch_next(self, recipient: str):
        assert recipient == "CEO"
        envelope = self.envelope
        self.envelope = None
        return envelope

    def ack_message(self, message_id: str, recipient: str):
        self.acked.append((message_id, recipient))

    def nack_message(self, message_id: str, recipient: str, reason: str):
        self.nacked.append((message_id, recipient, reason))

    def submit_envelope(self, envelope: dict, routing_hints=None):
        self.submitted.append((envelope, routing_hints or {}))
        return envelope["id"]


def envelope(task_type: str, payload: dict | None = None) -> dict:
    return {
        "id": "ceo-msg-1",
        "timestamp": "2026-04-30T12:00:00Z",
        "sender": "HR",
        "recipient": "CEO",
        "task_type": task_type,
        "context": {},
        "payload": payload or {},
        "status": "pending",
        "error": "",
    }


def test_ceo_fetches_from_router_and_acks_after_handling_message():
    ceo = CeoAgent(name="CEO")
    client = FakeRouterClient(envelope("CEO_PING"))

    processed = ceo.process_one_router_message(router_client=client)

    assert processed is True
    assert client.acked == [("ceo-msg-1", "CEO")]
    assert client.nacked == []


def test_ceo_nacks_router_message_when_handler_fails():
    ceo = CeoAgent(name="CEO")
    client = FakeRouterClient(envelope("CEO_PING"))

    def fail(_envelope):
        raise RuntimeError("handler exploded")

    ceo.on_bus_envelope = fail  # type: ignore[method-assign]

    processed = ceo.process_one_router_message(router_client=client)

    assert processed is True
    assert client.acked == []
    assert len(client.nacked) == 1
    assert client.nacked[0][0] == "ceo-msg-1"
    assert "handler exploded" in client.nacked[0][2]


def test_ceo_processes_hr_mint_token_request_from_router():
    registry = CeoDistributionTokenRegistry(executive_name="CEO")
    ceo = CeoAgent(name="CEO", distribution_registry=registry)
    client = FakeRouterClient(
        envelope(
            "MINT_TOKENS",
            {
                "scenario_id": "STANDARD_DELEGATION",
                "quantity": 10,
                "holder": "HR",
                "cost_per_send": 1,
            },
        )
    )

    processed = ceo.process_one_router_message(router_client=client)

    assert processed is True
    assert client.acked == [("ceo-msg-1", "CEO")]
    assert registry.is_registered("STANDARD_DELEGATION")
    assert registry.balance("HR", "STANDARD_DELEGATION") == 10


def test_ceo_can_send_envelope_through_router_client():
    ceo = CeoAgent(name="CEO")
    client = FakeRouterClient()

    message_id = ceo.send_router_envelope(
        recipient="HR",
        task_type="RECRUIT_TALENT",
        payload={"directive": "Recruit 2 ML contractors."},
        router_client=client,
        urgency="high",
    )

    assert message_id == client.submitted[0][0]["id"]
    assert client.submitted[0][0]["sender"] == "CEO"
    assert client.submitted[0][0]["recipient"] == "HR"
    assert client.submitted[0][0]["task_type"] == "RECRUIT_TALENT"
    assert client.submitted[0][1]["urgency"] == "high"
