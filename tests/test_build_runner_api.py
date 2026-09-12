from __future__ import annotations

import time

import requests
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
        api_port=9998,
    )
    return TestClient(create_app(settings)), settings.admin_secret


_EMBEDDED_SOURCE_BODY = (
    "## Engineering Request\n\nBuild a greeter.\n\n"
    "## Generated Files\n\n- `greeter.py`\n\n"
    "## Generated Source\n\n"
    "### `greeter.py`\n\n"
    "```python\n"
    "class Greeter:\n"
    "    def greet(self, name):\n"
    "        return f'Hello, {name}!'\n"
    "```\n"
)


def test_builds_run_hosts_generated_code_and_stop_tears_it_down(tmp_path, monkeypatch):
    """End-to-end: an artifact with embedded generated source, when run,
    actually spins up a live process that calls the real generated method --
    and stop actually tears it back down. This is the "host generated apps"
    feature the control plane's Builds page exposes as a Run/Stop button."""
    client, admin = _client(tmp_path, monkeypatch)
    artifact = write_agent_artifact(
        "Engineering", title="Engineering Feature Implementation",
        artifact_type="engineering", body=_EMBEDDED_SOURCE_BODY,
    )
    artifact_id = artifact["artifact_id"]

    try:
        run_response = client.post(f"/builds/{artifact_id}/run", headers={"X-Admin-Secret": admin})
        assert run_response.status_code == 200, run_response.text
        run = run_response.json()
        assert run["running"] is True
        assert run["class_name"] == "Greeter"
        assert run["init_error"] is None

        call = requests.post(f"{run['url']}/call/greet", json={"args": ["World"]}, timeout=5)
        assert call.json() == {"result": "Hello, World!"}

        listing = client.get("/builds/running", headers={"X-Admin-Secret": admin})
        assert any(r["artifact_id"] == artifact_id for r in listing.json())

        stop_response = client.post(f"/builds/{artifact_id}/stop", headers={"X-Admin-Secret": admin})
        assert stop_response.json() == {"stopped": True}

        time.sleep(0.3)
        try:
            requests.get(run["url"], timeout=2)
            assert False, "expected the hosted process to be torn down after stop"
        except requests.exceptions.ConnectionError:
            pass
    finally:
        client.post(f"/builds/{artifact_id}/stop", headers={"X-Admin-Secret": admin})


def test_builds_run_without_embedded_source_returns_400(tmp_path, monkeypatch):
    client, admin = _client(tmp_path, monkeypatch)
    artifact = write_agent_artifact(
        "Engineering", title="Engineering Feature Implementation",
        artifact_type="engineering", body="## Engineering Request\n\nNo source embedded.\n",
    )

    response = client.post(f"/builds/{artifact['artifact_id']}/run", headers={"X-Admin-Secret": admin})

    assert response.status_code == 400
    assert "no embedded generated source" in response.json()["detail"]


def test_builds_run_requires_admin_secret(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.post("/builds/art-does-not-exist/run")
    assert response.status_code == 401
