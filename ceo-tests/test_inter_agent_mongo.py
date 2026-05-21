"""Integration tests for Mongo inter-agent store (skipped if pymongo/MongoDB unavailable)."""

from __future__ import annotations

import uuid

import pytest

from enterprise_paths import inter_agent_mongo_uri


def _mongo_reachable() -> bool:
    try:
        from pymongo import MongoClient
    except ImportError:
        return False
    try:
        c = MongoClient(inter_agent_mongo_uri(), serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        c.close()
        return True
    except Exception:
        return False


@pytest.fixture
def store():
    pytest.importorskip("pymongo")
    from inter_agent_mongo import InterAgentMongoStore

    if not _mongo_reachable():
        pytest.skip("MongoDB not reachable (start mongod or set MONGO_URI)")
    # Atlas enforces max DB name length of 38 bytes.
    s = InterAgentMongoStore(
        db_name=f"tia_{uuid.uuid4().hex[:16]}",
    )
    yield s
    s._client.drop_database(s._db.name)
    s.close()


def test_enqueue_receive_fifo(store):
    e1 = {
        "id": "m-1",
        "timestamp": "",
        "sender": "CEO",
        "recipient": "HR",
        "task_type": "TASK",
        "context": {},
        "payload": {"n": 1},
        "status": "pending",
        "error": "",
    }
    e2 = {**e1, "id": "m-2", "payload": {"n": 2}}
    assert store.record_and_enqueue(e1)["queued"] is True
    assert store.record_and_enqueue(e2)["queued"] is True
    assert store.pending_count("HR") == 2
    got1 = store.pop_next_for_recipient("HR")
    assert got1 and got1.get("id") == "m-1"
    got2 = store.pop_next_for_recipient("HR")
    assert got2 and got2.get("id") == "m-2"
    assert store.pop_next_for_recipient("HR") is None


def test_duplicate_id_is_idempotent(store):
    env = {
        "id": "dup-1",
        "timestamp": "",
        "sender": "A",
        "recipient": "B",
        "task_type": "T",
        "context": {},
        "payload": {},
        "status": "pending",
        "error": "",
    }
    r1 = store.record_and_enqueue(env)
    r2 = store.record_and_enqueue(env)
    assert r1["queued"] is True
    assert r2["duplicate"] is True
    assert r2["queued"] is False
    assert store.pending_count("B") == 1
