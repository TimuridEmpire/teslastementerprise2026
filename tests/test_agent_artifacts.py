from __future__ import annotations

import json
from pathlib import Path

from enterprise_router.agent_artifacts import (
    envelope_prompt_json,
    poll_one_router_message,
    write_agent_artifact,
)
from message_schema import Message


def test_write_agent_artifact_creates_markdown(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))

    record = write_agent_artifact(
        "CEO",
        title="Q2 Strategy",
        body="Focus on router observability.",
        artifact_type="strategy",
        metadata={"quarter": "Q2"},
    )

    path = Path(record["path"])
    assert path.exists()
    assert path.suffix == ".md"
    assert "CEO" in path.read_text(encoding="utf-8")
    assert record["agent_name"] == "CEO"
    assert (tmp_path / "artifacts" / "ceo").is_dir()


def test_envelope_prompt_json_extracts_payload_fields():
    envelope = Message.create(
        sender="PM",
        recipient="CEO",
        task_type="CEO_REASONING_LOOP",
        payload={"message": "Plan Q2 roadmap", "departments": ["PM Agent"]},
    ).to_dict()

    extracted = envelope_prompt_json(envelope)
    assert extracted["prompt"] == "Plan Q2 roadmap"
    assert extracted["sender"] == "PM"
    assert extracted["payload"]["departments"] == ["PM Agent"]


def test_poll_one_router_message_logs_and_acks():
    envelope = Message.create(
        sender="HR",
        recipient="CEO",
        task_type="CEO_PING",
        payload={"prompt": "status check"},
    ).to_dict()
    queue = [envelope]
    acked: list[tuple[str, str]] = []
    logged: list[str] = []

    def fetch_next(recipient: str):
        assert recipient == "CEO"
        return queue.pop(0) if queue else None

    def ack(message_id: str, recipient: str) -> None:
        acked.append((message_id, recipient))

    def nack(message_id: str, recipient: str, reason: str) -> None:
        raise AssertionError(f"unexpected nack: {reason}")

    processed = poll_one_router_message(
        recipient="CEO",
        fetch_next=fetch_next,
        ack=ack,
        nack=nack,
        handler=lambda env: {"handled": env["task_type"]},
        log_prompt_json=True,
    )

    assert processed is True
    assert len(acked) == 1
    assert envelope_prompt_json(envelope)["prompt"] == "status check"
