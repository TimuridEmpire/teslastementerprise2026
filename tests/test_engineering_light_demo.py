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


def sample_manager_intervention(instruction: str = "Build a scientific calculator.") -> dict:
    """Shape sent by website/components/chat/CommandChat.tsx's `/eng <text>`
    command: POST /manager/interventions -> EnterpriseRouter.
    submit_manager_intervention() always folds the free-text instruction
    into payload["instruction"]."""
    return {
        "id": "eng-msg-2",
        "timestamp": "2026-05-26T00:00:00Z",
        "sender": "MANAGER",
        "recipient": "Engineering",
        "task_type": "MANAGER_INTERVENTION",
        "context": {"source": "command_chat"},
        "payload": {"instruction": instruction},
        "status": "pending",
        "error": "",
    }


def test_augment_spec_with_rag_context_puts_the_real_spec_first(monkeypatch):
    """Regression test: reproduced live, a request for "a weather app" built
    a calculator instead, because retrieve_rag_context() returned a prior,
    similar-looking calculator spec that used to be prepended *before* the
    real instruction -- the local model fixated on the retrieved text
    instead of the actual spec. The real spec must now come first, and the
    retrieved block must be unambiguously marked as reference-only."""
    module = load_engineering_module()
    monkeypatch.setattr(
        module,
        "retrieve_rag_context",
        lambda query, **kwargs: [{"agent_name": "Engineering", "title": "Old Calculator", "score": 0.9, "snippet": "Feature: Calculator..."}],
    )
    monkeypatch.setattr(
        module,
        "format_rag_context_block",
        lambda hits, **kwargs: "## Related prior engineering specs/code\n- [Engineering] Old Calculator: Feature: Calculator...",
    )

    agent = module.EngineeringAgent(db=None)
    real_spec = "Feature: Weather Lookup App\nDescription: Build a weather classification module."
    augmented = agent._augment_spec_with_rag_context(real_spec)

    assert augmented.startswith(real_spec)
    assert augmented.index(real_spec) < augmented.index("Old Calculator")
    assert "background only" in augmented.lower()
    assert "do not implement" in augmented.lower()


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


def test_engineering_handles_manager_intervention_from_chat_eng_command(monkeypatch):
    """Regression test: the website Chat page's `/eng <request>` command
    sends task_type MANAGER_INTERVENTION (Engineering is registered to
    accept it — scripts/bootstrap_router_agents.py) but engineering_agent.py
    previously had no handler for it, so every `/eng` request errored out
    instead of building anything."""
    module = load_engineering_module()
    monkeypatch.setenv("ENGINEERING_LIGHT_DEMO", "1")
    monkeypatch.setattr(module, "write_agent_artifact", lambda *args, **kwargs: {"artifact_id": "art-calc"})
    monkeypatch.setattr(module.EngineeringAgent, "_generated_files", lambda _self: [])

    agent = module.EngineeringAgent(db=None)
    response = agent.handle_message(sample_manager_intervention("Build a scientific calculator."))

    assert response["sender"] == "Engineering"
    assert response["recipient"] == "MANAGER"
    assert response["task_type"] == "FEATURE_RESPONSE"
    assert response["status"] == "done"
    assert response["payload"]["artifact_id"] == "art-calc"
    assert response["payload"]["details"]["status"] == "light_demo"
    assert "scientific calculator" in response["payload"]["details"]["spec_preview"]


def test_engineering_manager_intervention_without_instruction_fails_cleanly(monkeypatch):
    module = load_engineering_module()
    monkeypatch.setenv("ENGINEERING_LIGHT_DEMO", "1")
    monkeypatch.setattr(module, "write_agent_artifact", lambda *args, **kwargs: {"artifact_id": "art-err"})
    monkeypatch.setattr(module.EngineeringAgent, "_generated_files", lambda _self: [])

    agent = module.EngineeringAgent(db=None)
    message = sample_manager_intervention("")
    message["payload"] = {}

    response = agent.handle_message(message)

    assert response["status"] == "error"
    assert response["recipient"] == "MANAGER"
    assert "instruction" in response["payload"]["error"]
