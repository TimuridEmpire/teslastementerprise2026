from __future__ import annotations

from fastapi.testclient import TestClient

import enterprise_router.build_runner as build_runner
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


def test_builds_run_refuses_by_default_hosting_disabled(tmp_path, monkeypatch):
    """Fail-closed by default at the API layer too: a fresh install must not
    expose code execution until an operator explicitly opts in."""
    monkeypatch.delenv("ENTERPRISE_ROUTER_ENABLE_BUILD_HOSTING", raising=False)
    client, admin = _client(tmp_path, monkeypatch)
    artifact = write_agent_artifact(
        "Engineering", title="Engineering Feature Implementation",
        artifact_type="engineering", body=_EMBEDDED_SOURCE_BODY,
    )

    response = client.post(f"/builds/{artifact['artifact_id']}/run", headers={"X-Admin-Secret": admin})

    assert response.status_code == 403
    assert "disabled by policy" in response.json()["detail"]


def test_builds_run_refuses_without_docker_even_when_enabled(tmp_path, monkeypatch):
    """Real behavior in this environment (no Docker installed here), not
    mocked: enabling the policy flag alone must not be enough to run
    unsandboxed code -- Docker has to actually be present."""
    monkeypatch.setenv("ENTERPRISE_ROUTER_ENABLE_BUILD_HOSTING", "1")
    client, admin = _client(tmp_path, monkeypatch)
    artifact = write_agent_artifact(
        "Engineering", title="Engineering Feature Implementation",
        artifact_type="engineering", body=_EMBEDDED_SOURCE_BODY,
    )

    response = client.post(f"/builds/{artifact['artifact_id']}/run", headers={"X-Admin-Secret": admin})

    assert response.status_code == 503
    assert "Docker was not found" in response.json()["detail"]


def test_builds_run_without_embedded_source_returns_400(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_ROUTER_ENABLE_BUILD_HOSTING", "1")
    monkeypatch.setattr(build_runner, "docker_available", lambda: True)
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
