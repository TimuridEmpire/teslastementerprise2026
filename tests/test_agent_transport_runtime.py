from __future__ import annotations

import pytest

import agent_transport
from agent_transport import AGENT_CEO, AGENT_PM, make_envelope
from enterprise_router_client import EnterpriseRouterClient


ROUTER_ENV_KEYS = (
    "ENTERPRISE_ROUTER_API_URL",
    "ENTERPRISE_ROUTER_URL",
    "ENTERPRISE_ROUTER_AGENT_NAME",
    "ENTERPRISE_AGENT_NAME",
    "ENTERPRISE_ROUTER_AGENT_API_KEY",
    "ENTERPRISE_AGENT_API_KEY",
    "CEO_AGENT_API_KEY",
    "ENTERPRISE_ROUTER_ALLOW_LOCAL_FALLBACK",
    "ENTERPRISE_ROUTER_OFFLINE_DEMO",
)


def clear_router_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ROUTER_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def sample_envelope() -> dict:
    return make_envelope(
        sender=AGENT_CEO,
        recipient=AGENT_PM,
        task_type="DEFINE_Q2_ROADMAP",
        payload={"business_goal": "Increase SaaS revenue"},
    )


def test_submit_requires_enterprise_router_config_by_default(monkeypatch):
    clear_router_env(monkeypatch)

    with pytest.raises(RuntimeError, match="Enterprise Router is required"):
        agent_transport.submit(sample_envelope())


def test_local_message_bus_requires_explicit_offline_demo_mode(monkeypatch):
    clear_router_env(monkeypatch)
    monkeypatch.setenv("ENTERPRISE_ROUTER_OFFLINE_DEMO", "1")

    message_id = agent_transport.submit(sample_envelope())
    received = agent_transport.receive(AGENT_PM)

    assert message_id
    assert received is not None
    assert received["recipient"] == AGENT_PM


def test_legacy_local_fallback_flag_is_not_enough(monkeypatch):
    clear_router_env(monkeypatch)
    monkeypatch.setenv("ENTERPRISE_ROUTER_ALLOW_LOCAL_FALLBACK", "1")

    with pytest.raises(RuntimeError, match="Enterprise Router is required"):
        agent_transport.submit(sample_envelope())


def test_enterprise_router_client_from_env_requires_complete_config(monkeypatch):
    clear_router_env(monkeypatch)

    with pytest.raises(RuntimeError, match="Missing Enterprise Router configuration"):
        EnterpriseRouterClient.from_env(agent_name=AGENT_CEO)


class FakeRouterClient:
    def __init__(self, envelopes: list[dict]):
        self.envelopes = list(envelopes)
        self.acked: list[tuple[str, str]] = []

    def fetch_next(self, recipient: str):
        assert recipient == AGENT_PM
        if not self.envelopes:
            return None
        return self.envelopes.pop(0)

    def ack(self, message_id: str, recipient: str):
        self.acked.append((message_id, recipient))


def test_drain_mailbox_uses_router_fetch_and_ack_when_configured(monkeypatch):
    clear_router_env(monkeypatch)
    monkeypatch.setenv("ENTERPRISE_ROUTER_API_URL", "http://router.local")
    monkeypatch.setenv("ENTERPRISE_ROUTER_AGENT_NAME", AGENT_PM)
    monkeypatch.setenv("ENTERPRISE_ROUTER_AGENT_API_KEY", "secret")
    first = sample_envelope()
    second = {**sample_envelope(), "id": "msg-second"}
    fake_client = FakeRouterClient([first, second])
    monkeypatch.setattr(agent_transport, "client", lambda _agent_name=None: fake_client)

    messages = agent_transport.drain_mailbox(AGENT_PM)

    assert [message["id"] for message in messages] == [first["id"], "msg-second"]
    assert fake_client.acked == [(first["id"], AGENT_PM), ("msg-second", AGENT_PM)]
