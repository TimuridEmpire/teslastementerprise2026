from __future__ import annotations

import json
from pathlib import Path

from enterprise_router.agent_artifacts import (
    envelope_prompt_json,
    get_agent_artifact,
    list_agent_artifacts,
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


def test_write_agent_artifact_appends_safe_index_record(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))

    record = write_agent_artifact(
        "CEO",
        title="Q2 Strategy",
        body="Focus on router observability.",
        artifact_type="strategy",
        metadata={"quarter": "Q2"},
        source_message_id="msg-123",
        source_task_type="CEO_REASONING_LOOP",
    )

    index_path = tmp_path / "artifacts" / "index.jsonl"
    assert index_path.exists()
    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "artifact_id": record["artifact_id"],
            "agent_name": "CEO",
            "artifact_type": "strategy",
            "title": "Q2 Strategy",
            "filename": record["filename"],
            "agent_slug": "ceo",
            "created_at": record["created_at"],
            "metadata": {"quarter": "Q2"},
            "source_message_id": "msg-123",
            "source_task_type": "CEO_REASONING_LOOP",
        }
    ]
    assert "path" not in rows[0]


def test_list_agent_artifacts_filters_by_agent_newest_first(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))

    first = write_agent_artifact("CEO", title="First", body="older")
    hr = write_agent_artifact("HR", title="HR Plan", body="hire")
    second = write_agent_artifact("CEO", title="Second", body="newer")

    records = list_agent_artifacts(agent_name="CEO", limit=10)

    assert [r["artifact_id"] for r in records] == [second["artifact_id"], first["artifact_id"]]
    assert all(r["agent_name"] == "CEO" for r in records)
    assert hr["artifact_id"] not in [r["artifact_id"] for r in records]
    assert all("path" not in r for r in records)


def test_get_agent_artifact_returns_markdown_content_without_path(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    record = write_agent_artifact(
        "CEO",
        title="Executive Summary",
        body="## Decision\n\nInvest in router visibility.",
    )

    detail = get_agent_artifact(record["artifact_id"])

    assert detail["artifact_id"] == record["artifact_id"]
    assert detail["content"].startswith("# Executive Summary")
    assert "Invest in router visibility." in detail["content"]
    assert "path" not in detail


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
