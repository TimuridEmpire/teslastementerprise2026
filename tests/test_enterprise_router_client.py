from __future__ import annotations

from enterprise_router_client import EnterpriseRouterClient, router_configured


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

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(
            {"method": "GET", "url": url, "params": params, "headers": headers, "timeout": timeout}
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


def test_submit_message_alias_uses_same_router_contract():
    session = FakeSession()
    session.next_payload = {"message_id": "msg-1"}
    client = EnterpriseRouterClient(
        base_url="http://router.local",
        agent_name="HR",
        api_key="secret",
        session=session,
    )

    message_id = client.submit_message(sample_envelope())

    assert message_id == "msg-1"
    assert session.calls[0]["url"] == "http://router.local/messages"


def test_peek_returns_envelopes_from_router_queue_items():
    session = FakeSession()
    session.next_payload = [{"envelope": sample_envelope(), "computed_priority": 150}]
    client = EnterpriseRouterClient(
        base_url="http://router.local",
        agent_name="HR",
        api_key="secret",
        session=session,
    )

    rows = client.peek(limit=5)

    assert rows == [sample_envelope()]
    assert session.calls[0]["method"] == "GET"
    assert session.calls[0]["url"] == "http://router.local/messages/peek"
    assert session.calls[0]["params"] == {"recipient": "HR", "limit": 5}


def test_ack_alias_posts_ack_endpoint():
    session = FakeSession()
    session.next_payload = {"message_id": "msg-1", "status": "done"}
    client = EnterpriseRouterClient(
        base_url="http://router.local",
        agent_name="HR",
        api_key="secret",
        session=session,
    )

    client.ack("msg-1", "HR")

    assert session.calls[0]["url"] == "http://router.local/messages/msg-1/ack"
    assert session.calls[0]["json"] == {"recipient": "HR"}


def test_router_configured_accepts_legacy_and_router_env_names(monkeypatch):
    monkeypatch.delenv("ENTERPRISE_ROUTER_API_URL", raising=False)
    monkeypatch.delenv("ENTERPRISE_ROUTER_AGENT_NAME", raising=False)
    monkeypatch.delenv("ENTERPRISE_ROUTER_AGENT_API_KEY", raising=False)
    monkeypatch.setenv("ENTERPRISE_ROUTER_URL", "http://router.local")
    monkeypatch.setenv("ENTERPRISE_AGENT_NAME", "HR")
    monkeypatch.setenv("ENTERPRISE_AGENT_API_KEY", "secret")

    assert router_configured()
