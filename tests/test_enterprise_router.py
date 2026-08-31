"""Tests for enterprise router service (sqlite backend)."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone

import pytest

from enterprise_router.models import AgentRecord, MessageEnvelope, RegistrationRequest, RoutingHints
from enterprise_router.service import EnterpriseRouter


def _envelope(sender: str, recipient: str, task: str) -> MessageEnvelope:
    return MessageEnvelope(
        id=f"msg-{uuid.uuid4().hex[:8]}",
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        sender=sender,
        recipient=recipient,
        task_type=task,
        context={},
        payload={"x": 1},
        status="pending",
    )


@pytest.fixture
def router(tmp_path):
    db = str(tmp_path / "router.db")
    r = EnterpriseRouter(db_path=db, shared_secret="test-secret")
    r.register_agent(AgentRecord(agent_name="CEO", role="executive"))
    r.register_agent(AgentRecord(agent_name="HR", role="hr"))
    r.issue_api_key("CEO")
    r.issue_api_key("HR")
    return r


def test_submit_fetch_ack(router: EnterpriseRouter):
    env = _envelope("CEO", "HR", "TALENT_REALLOCATION")
    mid = router.submit_message(env, RoutingHints(priority=1))
    assert mid == env.id

    item = router.fetch_next("HR")
    assert item is not None
    assert item.envelope.id == env.id

    router.ack_message(env.id, "HR")
    assert router.fetch_next("HR") is None


def test_queue_item_to_dict_matches_website_ready_contract(router: EnterpriseRouter):
    env = _envelope("CEO", "HR", "TALENT_REALLOCATION")
    env.context = {
        "provenance_source": "ceo_agent",
        "provenance_agent": "CEO",
        "provenance_trust_level": 95,
    }
    router.submit_message(
        env,
        RoutingHints(priority=7, ttl_seconds=600, dedupe_key="talent-1"),
    )

    item = router.fetch_next("HR")

    assert item is not None
    assert item.to_dict() == {
        "queue_id": item.queue_id,
        "message_id": item.message_id,
        "recipient": "HR",
        "envelope": env.to_dict(),
        "computed_priority": 7,
        "attempt_count": 0,
        "lease_until": item.lease_until,
        "delivery_state": "leased",
        "blocked_reason": "",
        "enqueued_at": item.enqueued_at,
        "ttl_expires_at": item.ttl_expires_at,
        "visible_at": item.visible_at,
        "provenance_source": "ceo_agent",
        "provenance_agent": "CEO",
        "provenance_trust_level": 95,
        "ttl_seconds": 600,
        "dedupe_key": "talent-1",
    }


def test_urgency_hint_maps_to_computed_priority(router: EnterpriseRouter):
    env = _envelope("CEO", "HR", "TALENT_REALLOCATION")
    router.submit_message(env, RoutingHints.from_mapping({"urgency": "high"}))

    item = router.fetch_next("HR")

    assert item is not None
    assert item.to_dict()["computed_priority"] == 150


def test_registration_flow(router: EnterpriseRouter):
    name = router.request_registration(
        RegistrationRequest(
            agent_name="PM",
            role="product",
            secret_token="test-secret",
        )
    )
    assert name == "PM"
    key = router.approve_registration("PM", "admin", issue_api_key=True)
    assert key
    router.authenticate_agent("PM", key)


def test_demo_agent_allowed_task_contract_permits_live_chain(tmp_path):
    from scripts.bootstrap_router_agents import AGENTS

    db = str(tmp_path / "router.db")
    router = EnterpriseRouter(db_path=db, shared_secret="test-secret")
    contracts = {
        name: allowed_task_types
        for name, _role, _hierarchy, _trust, allowed_task_types in AGENTS
    }
    for agent_name, task_types in contracts.items():
        router.register_agent(
            AgentRecord(
                agent_name=agent_name,
                role=agent_name.lower(),
                allowed_task_types=task_types,
            )
        )

    demo_messages = [
        _envelope("MANAGER", "CEO", "CEO_REASONING_LOOP"),
        _envelope("CEO", "PM", "CEO_STRATEGY_DIRECTIVE"),
        _envelope("PM", "Engineering", "IMPLEMENT_FEATURE"),
        _envelope("PM", "HR", "TALENT_REALLOCATION"),
        _envelope("PM", "Marketing", "LAUNCH_CAMPAIGN"),
        _envelope("Engineering", "PM", "FEATURE_RESPONSE"),
        _envelope("PM", "CEO", "PM_REPORT"),
        _envelope("CEO", "MANAGER", "AGENT_ARTIFACT_READY"),
    ]

    for envelope in demo_messages:
        assert router.submit_message(envelope, RoutingHints(priority=5)) == envelope.id
