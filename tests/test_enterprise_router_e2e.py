"""
End-to-end HTTP tests for the Enterprise Router FastAPI app.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from enterprise_router.api import create_app
from enterprise_router.config import RouterSettings


def _envelope(sender: str, recipient: str, task: str) -> dict:
    return {
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sender": sender,
        "recipient": recipient,
        "task_type": task,
        "context": {"e2e": True},
        "payload": {"note": "e2e"},
        "status": "pending",
        "error": "",
    }


@pytest.fixture
def router_client(tmp_path):
    settings = RouterSettings(
        backend="sqlite",
        sqlite_db_path=str(tmp_path / "e2e_router.db"),
        mongo_uri="mongodb://localhost:27017/",
        mongo_db_name="e2e_unused",
        shared_secret="reg-shared",
        admin_secret="admin-e2e",
        api_host="127.0.0.1",
        api_port=9999,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, settings


def _register_agent(client: TestClient, admin: str, name: str, role: str) -> str:
    resp = client.post(
        "/agents",
        headers={"X-Admin-Secret": admin},
        json={
            "agent_name": name,
            "role": role,
            "hierarchy_level": 50,
            "trust_level": 50,
            "issue_api_key": True,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("api_key")
    return data["api_key"]


def _agent_headers(agent_name: str, api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Agent-Id": agent_name,
    }


def test_health(router_client):
    client, settings = router_client
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "backend": settings.backend}


def test_registration_approve_and_message_lifecycle(router_client):
    client, settings = router_client
    admin = settings.admin_secret

    reg = client.post(
        "/registrations/request",
        json={
            "agent_name": "PM",
            "role": "product",
            "secret_token": settings.shared_secret,
        },
    )
    assert reg.status_code == 200
    assert reg.json()["status"] == "pending"

    approve = client.post(
        "/registrations/PM/approve",
        headers={"X-Admin-Secret": admin},
        json={"approver": "admin", "issue_api_key": True},
    )
    assert approve.status_code == 200
    pm_key = approve.json()["api_key"]

    ceo_key = _register_agent(client, admin, "CEO", "executive")
    hr_key = _register_agent(client, admin, "HR", "hr")

    env = _envelope("CEO", "HR", "TALENT_REALLOCATION")
    submit = client.post(
        "/messages",
        headers=_agent_headers("CEO", ceo_key),
        json={"message": env, "routing_hints": {"priority": 2}},
    )
    assert submit.status_code == 200
    assert submit.json()["message_id"] == env["id"]

    wrong_sender = client.post(
        "/messages",
        headers=_agent_headers("CEO", ceo_key),
        json={
            "message": {**env, "id": f"msg-{uuid.uuid4().hex[:8]}", "sender": "PM"},
            "routing_hints": {},
        },
    )
    assert wrong_sender.status_code == 403

    fetch = client.post(
        "/messages/fetch-next",
        headers=_agent_headers("HR", hr_key),
        json={"recipient": "HR"},
    )
    assert fetch.status_code == 200
    body = fetch.json()
    assert body["envelope"]["id"] == env["id"]
    assert body["computed_priority"] == 2
    assert body["delivery_state"] == "leased"
    assert body["attempt_count"] == 0
    assert body["lease_until"]
    assert body["blocked_reason"] == ""
    assert body["ttl_seconds"] is None
    assert body["dedupe_key"] is None
    assert body["provenance_source"] is None
    assert body["provenance_agent"] is None
    assert body["provenance_trust_level"] is None

    peek = client.get(
        "/messages/peek",
        headers=_agent_headers("HR", hr_key),
        params={"recipient": "HR", "limit": 5},
    )
    assert peek.status_code == 200
    assert isinstance(peek.json(), list)

    ack = client.post(
        f"/messages/{env['id']}/ack",
        headers=_agent_headers("HR", hr_key),
        json={"recipient": "HR"},
    )
    assert ack.status_code == 200

    empty = client.post(
        "/messages/fetch-next",
        headers=_agent_headers("HR", hr_key),
        json={"recipient": "HR"},
    )
    assert empty.status_code == 200
    assert empty.json() == {}

    pm_submit = client.post(
        "/messages",
        headers=_agent_headers("PM", pm_key),
        json={
            "message": _envelope("PM", "CEO", "PM_REPORT"),
            "routing_hints": {},
        },
    )
    assert pm_submit.status_code == 200

    audit = client.get(
        "/audit",
        headers={"X-Admin-Secret": admin},
        params={"limit": 5},
    )
    assert audit.status_code == 200
    assert len(audit.json()) >= 1


def test_peek_and_queue_view_return_consistent_rich_queue_items(router_client):
    client, settings = router_client
    admin = settings.admin_secret
    ceo_key = _register_agent(client, admin, "CEO", "executive")
    hr_key = _register_agent(client, admin, "HR", "hr")

    env = _envelope("CEO", "HR", "HIRING_REQUEST")
    env["context"] = {
        "provenance_source": "ceo_agent",
        "provenance_agent": "CEO",
        "provenance_trust_level": 88,
    }
    submit = client.post(
        "/messages",
        headers=_agent_headers("CEO", ceo_key),
        json={
            "message": env,
            "routing_hints": {
                "priority": 9,
                "ttl_seconds": 300,
                "dedupe_key": "hire-1",
            },
        },
    )
    assert submit.status_code == 200

    peek = client.get(
        "/messages/peek",
        headers=_agent_headers("HR", hr_key),
        params={"recipient": "HR", "limit": 5},
    )
    queue = client.get(
        "/queue/HR",
        headers=_agent_headers("HR", hr_key),
    )

    assert peek.status_code == 200
    assert queue.status_code == 200
    assert peek.json() == queue.json()
    item = peek.json()[0]
    assert item == {
        "queue_id": item["queue_id"],
        "message_id": item["message_id"],
        "recipient": "HR",
        "envelope": env,
        "computed_priority": 9,
        "attempt_count": 0,
        "lease_until": None,
        "delivery_state": "pending",
        "blocked_reason": "",
        "enqueued_at": item["enqueued_at"],
        "ttl_expires_at": item["ttl_expires_at"],
        "visible_at": item["visible_at"],
        "provenance_source": "ceo_agent",
        "provenance_agent": "CEO",
        "provenance_trust_level": 88,
        "ttl_seconds": 300,
        "dedupe_key": "hire-1",
    }


def test_manager_intervention_requires_manager_role(router_client):
    client, settings = router_client
    admin = settings.admin_secret
    ceo_key = _register_agent(client, admin, "CEO", "executive")
    _register_agent(client, admin, "MANAGER", "manager")

    denied = client.post(
        "/manager/interventions",
        headers=_agent_headers("CEO", ceo_key),
        json={
            "recipient": "HR",
            "instruction": "Pause hiring",
            "priority": "high",
        },
    )
    assert denied.status_code == 403
