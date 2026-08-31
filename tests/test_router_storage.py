"""Pytest coverage for RouterStorage backends and create_storage factory."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from enterprise_router.models import (
    AgentApiKeyRecord,
    AgentRecord,
    MessageEnvelope,
    RegistrationRequest,
)
from enterprise_router.router_storage import create_storage
from enterprise_router.service import EnterpriseRouter


def _envelope(sender: str, recipient: str, task: str) -> MessageEnvelope:
    return MessageEnvelope(
        id=f"msg-{uuid.uuid4().hex[:8]}",
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        sender=sender,
        recipient=recipient,
        task_type=task,
        context={},
        payload={},
        status="pending",
    )


@pytest.fixture
def store(tmp_path):
    return create_storage(db_path=str(tmp_path / "router_storage.db"))


def test_register_agent_and_api_key(store):
    store.register_agent(AgentRecord(agent_name="CEO", role="executive"))
    assert store.get_agent("CEO") is not None
    store.store_api_key(
        AgentApiKeyRecord(
            agent_name="CEO",
            key_hash="abc123",
            label="default",
            created_at="2026-01-01T00:00:00Z",
        )
    )
    key = store.get_api_key("CEO")
    assert key is not None
    assert key["key_hash"] == "abc123"


def test_registration_lifecycle(store):
    req = RegistrationRequest(
        agent_name="PM",
        role="product",
        secret_token="secret",
    )
    store.request_registration(req, token_hash="hashed")
    row = store.get_registration_request("PM")
    assert row is not None
    assert row["status"] == "pending"
    assert store.update_registration_status("PM", "approved", "2026-01-02T00:00:00Z", "admin")
    row = store.get_registration_request("PM")
    assert row["status"] == "approved"


def test_message_queue_lease_and_done(store):
    store.register_agent(AgentRecord(agent_name="HR", role="hr"))
    env = _envelope("CEO", "HR", "PING")
    store.insert_message(
        env,
        {"priority": 1, "dedupe_key": None, "ttl_expires_at": None, "enqueued_at": env.timestamp},
    )
    leased = store.lease_next_message("HR", "2026-01-01T00:05:00Z")
    assert leased is not None
    assert leased["message_id"] == env.id
    store.mark_message_done(env.id, "2026-01-01T00:06:00Z")
    assert store.lease_next_message("HR", "2026-01-01T00:07:00Z") is None


def test_queue_record_preserves_router_metadata_for_api_shape(store):
    store.register_agent(AgentRecord(agent_name="HR", role="hr"))
    env = _envelope("CEO", "HR", "PING")
    store.insert_message(
        env,
        {
            "priority": 11,
            "dedupe_key": "ping-1",
            "ttl_seconds": 120,
            "ttl_expires_at": "2026-01-01T00:02:00Z",
            "enqueued_at": env.timestamp,
        },
    )

    [record] = store.get_queue_records("HR")

    assert record["priority"] == 11
    assert record["attempts"] == 0
    assert record["state"] == "queued"
    assert record["lease_until"] is None
    assert record["dedupe_key"] == "ping-1"
    assert record["routing"]["ttl_seconds"] == 120
    assert record["routing"]["ttl_expires_at"] == "2026-01-01T00:02:00Z"
    assert record["error"] == ""


def test_dedupe_find(store):
    env = _envelope("CEO", "HR", "TASK")
    routing = {
        "priority": 0,
        "dedupe_key": "dedupe-1",
        "ttl_expires_at": None,
        "enqueued_at": env.timestamp,
    }
    store.insert_message(env, routing)
    found = store.find_message_by_dedupe("CEO", "HR", "TASK", "dedupe-1")
    assert found == env.id


def test_create_storage_factory(tmp_path):
    s = create_storage(db_path=str(tmp_path / "factory.db"))
    assert s.get_agent("missing") is None


def test_enterprise_router_uses_injected_storage(tmp_path):
    storage = create_storage(db_path=str(tmp_path / "svc.db"))
    router = EnterpriseRouter(storage=storage, shared_secret="reg")
    router.register_agent(AgentRecord(agent_name="CEO", role="executive"))
    router.register_agent(AgentRecord(agent_name="HR", role="hr"))
    env = _envelope("CEO", "HR", "TASK")
    from enterprise_router.models import RoutingHints

    mid = router.submit_message(env, RoutingHints())
    item = router.fetch_next("HR")
    assert item is not None
    assert item.message_id == mid
    router.ack_message(mid, "HR")
