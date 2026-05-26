from __future__ import annotations

import importlib.util
from pathlib import Path


def load_engineering_module():
    path = Path(__file__).resolve().parents[1] / "eng-agents" / "engineering_agent.py"
    spec = importlib.util.spec_from_file_location("engineering_agent_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_implement_feature() -> dict:
    return {
        "id": "eng-msg-1",
        "timestamp": "2026-05-26T00:00:00Z",
        "sender": "PM",
        "recipient": "Engineering",
        "task_type": "IMPLEMENT_FEATURE",
        "context": {"project_id": "project-1", "run_id": "run-1"},
        "payload": {
            "feature_id": "FT-001",
            "feature_name": "Live artifact panel",
            "spec": "Build a dashboard panel that renders live artifacts.",
            "acceptance_criteria": ["Shows newest artifact", "Does not show fake output as live"],
        },
        "status": "pending",
        "error": "",
    }


def test_engineering_light_demo_writes_artifact_and_returns_feature_response(monkeypatch):
    module = load_engineering_module()
    monkeypatch.setenv("ENGINEERING_LIGHT_DEMO", "1")
    monkeypatch.setattr(module, "write_agent_artifact", lambda *args, **kwargs: {"artifact_id": "art-eng"})
    monkeypatch.setattr(module.EngineeringAgent, "_generated_files", lambda _self: [])

    agent = module.EngineeringAgent(db=None)
    response = agent.handle_message(sample_implement_feature())

    assert response["sender"] == "Engineering"
    assert response["recipient"] == "PM"
    assert response["task_type"] == "FEATURE_RESPONSE"
    assert response["status"] == "done"
    assert response["payload"]["artifact_id"] == "art-eng"
    assert response["payload"]["details"]["status"] == "light_demo"
    assert response["payload"]["generated_files"] == []
