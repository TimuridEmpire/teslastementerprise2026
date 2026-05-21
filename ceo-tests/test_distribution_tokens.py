from __future__ import annotations

"""Tests for CEO distribution token registry and MessageBus gating."""

import datetime
import uuid

import pytest

from agent_backlog import AgentBacklog
from agents.ceo_agent import CeoAgent
from ceo_distribution_tokens import (
    CeoDistributionTokenRegistry,
    DistributionTokenError,
    resolve_distribution_scenario,
)
from message_bus import MessageBus


def _envelope(*, sender: str, recipient: str, task_type: str, context: dict | None = None):
    return {
        "id": f"req-{uuid.uuid4().hex[:6]}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sender": sender,
        "recipient": recipient,
        "task_type": task_type,
        "context": context or {},
        "payload": {},
        "status": "pending",
        "error": "",
    }


def test_resolve_scenario_from_context():
    env = _envelope(sender="PM", recipient="Eng", task_type="TASK", context={"distribution_scenario": "LAUNCH"})
    assert resolve_distribution_scenario(env) == "LAUNCH"
    env2 = _envelope(sender="PM", recipient="Eng", task_type="TASK", context={"prompt_scenario": " Q2 "})
    assert resolve_distribution_scenario(env2) == "Q2"
    env3 = _envelope(sender="PM", recipient="Eng", task_type="TASK", context={})
    assert resolve_distribution_scenario(env3) is None


def test_ceo_mint_assign_and_consume():
    reg = CeoDistributionTokenRegistry(executive_name="CEO")
    ceo = CeoAgent(name="CEO", distribution_registry=reg)
    ceo.register_distribution_scenario("LAUNCH", cost_per_send=2)
    ceo.mint_distribution_tokens("LAUNCH", 10, holder="CEO")
    ceo.assign_distribution_tokens("LAUNCH", to_holder="PM", quantity=4)
    assert reg.balance("CEO", "LAUNCH") == 6
    assert reg.balance("PM", "LAUNCH") == 4
    assert reg.try_consume("PM", "LAUNCH", 2)
    assert reg.balance("PM", "LAUNCH") == 2
    assert reg.try_consume("PM", "LAUNCH", 2)
    assert reg.balance("PM", "LAUNCH") == 0
    assert not reg.try_consume("PM", "LAUNCH", 2)


def test_non_executive_cannot_mint():
    reg = CeoDistributionTokenRegistry(executive_name="CEO")
    reg.register_scenario("X", acting_executive="CEO", cost_per_send=1)  # use register_scenario on reg with CEO
    with pytest.raises(PermissionError):
        reg.mint("X", 1, "PM", acting_executive="PM")


def test_bus_blocks_send_without_tokens(tmp_path):
    db = tmp_path / "b.db"
    log = tmp_path / "m.jsonl"
    reg = CeoDistributionTokenRegistry(executive_name="CEO")
    reg.register_scenario("RARE_BROADCAST", acting_executive="CEO", cost_per_send=1)
    reg.mint("RARE_BROADCAST", 0, "PM", acting_executive="CEO")

    bus = MessageBus(
        backlog=AgentBacklog(str(db)),
        json_log_path=str(log),
        distribution_tokens=reg,
        enforce_distribution_tokens=True,
    )

    env = _envelope(
        sender="PM",
        recipient="broadcast",
        task_type="ANNOUNCE",
        context={"prompt_scenario": "RARE_BROADCAST"},
    )
    with pytest.raises(DistributionTokenError) as ei:
        bus.send(env)
    assert ei.value.balance == 0
    assert ei.value.cost == 1

    reg.mint("RARE_BROADCAST", 1, "PM", acting_executive="CEO")
    bus.send(env)
    assert reg.balance("PM", "RARE_BROADCAST") == 0


def test_unregistered_scenario_does_not_gate(tmp_path):
    db = tmp_path / "b2.db"
    log = tmp_path / "m2.jsonl"
    reg = CeoDistributionTokenRegistry(executive_name="CEO")
    bus = MessageBus(
        backlog=AgentBacklog(str(db)),
        json_log_path=str(log),
        distribution_tokens=reg,
        enforce_distribution_tokens=True,
    )
    env = _envelope(
        sender="PM",
        recipient="X",
        task_type="T",
        context={"distribution_scenario": "NOT_REGISTERED"},
    )
    bus.send(env)  # should not raise


def test_register_scenario_on_registry():
    reg = CeoDistributionTokenRegistry()
    reg.register_scenario("S", acting_executive="CEO", cost_per_send=3)
    assert reg.cost_for("S") == 3
