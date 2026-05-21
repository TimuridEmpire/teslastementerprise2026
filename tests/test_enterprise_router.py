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
    r = EnterpriseRouter(backend="sqlite", db_path=db, shared_secret="test-secret")
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
