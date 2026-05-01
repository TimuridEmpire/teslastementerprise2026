from __future__ import annotations

from enterprise_router_client import EnterpriseRouterClient


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []
        self.next_payload = {}

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(
            {"method": "POST", "url": url, "json": json, "headers": headers, "timeout": timeout}
        )
        return FakeResponse(self.next_payload)


def sample_envelope() -> dict:
    return {
        "id": "msg-1",
        "timestamp": "2026-04-30T12:00:00Z",
        "sender": "HR",
        "recipient": "CEO",
        "task_type": "MINT_TOKENS",
        "context": {},
        "payload": {"scenario_id": "STANDARD_DELEGATION"},
        "status": "pending",
        "error": "",
    }


def test_submit_envelope_posts_to_enterprise_router_messages_endpoint():
    session = FakeSession()
    session.next_payload = {"message_id": "msg-1"}
    client = EnterpriseRouterClient(
        base_url="http://router.local/",
        agent_name="HR",
        api_key="secret",
        session=session,
    )

    message_id = client.submit_envelope(
        sample_envelope(),
        routing_hints={"urgency": "high"},
    )

    assert message_id == "msg-1"
    assert session.calls[0]["url"] == "http://router.local/messages"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer secret"
    assert session.calls[0]["headers"]["X-Agent-Id"] == "HR"
    assert session.calls[0]["json"]["message"]["sender"] == "HR"
    assert session.calls[0]["json"]["routing_hints"] == {"urgency": "high"}


def test_fetch_next_returns_envelope_from_router_queue_item():
    session = FakeSession()
    session.next_payload = {
        "envelope": sample_envelope(),
        "computed_priority": 150,
        "attempt_count": 0,
        "lease_until": "2026-04-30T12:01:00Z",
        "delivery_state": "leased",
        "blocked_reason": "",
    }
    client = EnterpriseRouterClient(
        base_url="http://router.local",
        agent_name="HR",
        api_key="secret",
        session=session,
    )

    envelope = client.fetch_next("HR")

    assert envelope == sample_envelope()
    assert session.calls[0]["url"] == "http://router.local/messages/fetch-next"
    assert session.calls[0]["json"] == {"recipient": "HR"}
