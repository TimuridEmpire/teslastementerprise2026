from __future__ import annotations

import json

from fastapi.testclient import TestClient

from enterprise_router.agent_artifacts import write_agent_artifact
from enterprise_router.api import create_app
from enterprise_router.config import RouterSettings


def _client(tmp_path, monkeypatch) -> tuple[TestClient, str]:
    monkeypatch.setenv("ENTERPRISE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    settings = RouterSettings(
        sqlite_db_path=str(tmp_path / "router.db"),
        shared_secret="shared",
        admin_secret="admin-secret",
        api_host="127.0.0.1",
        api_port=9999,
    )
    return TestClient(create_app(settings)), settings.admin_secret


def test_artifacts_api_lists_agent_artifacts_without_paths(tmp_path, monkeypatch):
    client, admin = _client(tmp_path, monkeypatch)
    ceo = write_agent_artifact("CEO", title="CEO Output", body="Board summary")
    write_agent_artifact("HR", title="HR Output", body="Hiring summary")

    response = client.get(
        "/artifacts",
        headers={"X-Admin-Secret": admin},
        params={"agent": "CEO", "limit": 20},
    )

    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "artifact_id": ceo["artifact_id"],
            "agent_name": "CEO",
            "artifact_type": "document",
            "title": "CEO Output",
            "filename": ceo["filename"],
            "agent_slug": "ceo",
            "created_at": ceo["created_at"],
            "metadata": {},
            "source_message_id": None,
            "source_task_type": None,
        }
    ]


def test_artifacts_api_returns_markdown_detail(tmp_path, monkeypatch):
    client, admin = _client(tmp_path, monkeypatch)
    artifact = write_agent_artifact(
        "CEO",
        title="CEO Strategy",
        body="## Recommendation\n\nShip artifact visibility.",
    )

    response = client.get(
        f"/artifacts/{artifact['artifact_id']}",
        headers={"X-Admin-Secret": admin},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["artifact_id"] == artifact["artifact_id"]
    assert body["title"] == "CEO Strategy"
    assert "Ship artifact visibility." in body["content"]
    assert "path" not in body


def test_artifacts_api_rejects_index_path_escape(tmp_path, monkeypatch):
    client, admin = _client(tmp_path, monkeypatch)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    (artifacts_dir / "index.jsonl").write_text(
        json.dumps(
            {
                "artifact_id": "art-escape",
                "agent_name": "CEO",
                "artifact_type": "document",
                "title": "Escape",
                "filename": outside.name,
                "agent_slug": "..",
                "created_at": "2026-05-25T00:00:00Z",
                "metadata": {},
                "source_message_id": None,
                "source_task_type": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    response = client.get(
        "/artifacts/art-escape",
        headers={"X-Admin-Secret": admin},
    )

    assert response.status_code == 404

