"""Unit tests for the enterprise message envelope schema."""

from __future__ import annotations

import pytest

from message_schema import Message, envelope_dict, normalize_envelope


def test_create_produces_valid_envelope():
    msg = Message.create(
        sender="CEO",
        recipient="PM",
        task_type="DEFINE_Q2_ROADMAP",
        context={"quarter": "Q2"},
        payload={"goal": "grow revenue"},
    )
    data = normalize_envelope(msg)
    assert data["sender"] == "CEO"
    assert data["recipient"] == "PM"
    assert data["status"] == "pending"
    assert data["id"].startswith("msg-")


def test_from_dict_round_trip():
    original = Message.create(sender="HR", recipient="CEO", task_type="MINT_TOKENS", payload={"n": 5})
    restored = Message.from_dict(original.to_dict())
    assert restored.sender == original.sender
    assert restored.payload == original.payload


def test_validate_rejects_bad_status():
    bad = Message.create(sender="A", recipient="B", task_type="T").to_dict()
    bad["status"] = "invalid"
    with pytest.raises(ValueError, match="status"):
        Message.validate_envelope(bad)


def test_normalize_fills_defaults():
    partial = {
        "id": "req-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "sender": "CEO",
        "recipient": "HR",
        "task_type": "TASK",
    }
    data = normalize_envelope(partial)
    assert data["context"] == {}
    assert data["payload"] == {}
    assert data["status"] == "pending"
    assert data["error"] == ""


def test_envelope_dict_accepts_message_instance():
    msg = Message.create(sender="X", recipient="Y", task_type="Z")
    assert envelope_dict(msg)["sender"] == "X"
