"""
Regression tests: the website Chat page's `/prod <request>` command sends
task_type MANAGER_INTERVENTION (PM is registered to accept it — see
scripts/bootstrap_router_agents.py) but pm_agent.py's dispatch had no case
for it, so it fell through to "unhandled task_type" and was silently acked
with no visible effect.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import mock


def load_pm_module():
    path = Path(__file__).resolve().parents[1] / "pm-agents" / "pm_agent.py"
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("pm_agent_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_manager_intervention(instruction: str = "Build a scientific calculator.") -> dict:
    """Shape sent by website/components/chat/CommandChat.tsx's `/prod <text>`
    command: POST /manager/interventions -> EnterpriseRouter.
    submit_manager_intervention() always folds the free-text instruction
    into payload["instruction"]."""
    return {
        "id": "pm-msg-1",
        "timestamp": "2026-05-26T00:00:00Z",
        "sender": "MANAGER",
        "recipient": "PM",
        "task_type": "MANAGER_INTERVENTION",
        "context": {"source": "command_chat"},
        "payload": {"instruction": instruction},
        "status": "pending",
        "error": "",
    }


def test_pm_handles_manager_intervention_from_chat_prod_command(monkeypatch):
    module = load_pm_module()
    monkeypatch.setattr(
        module,
        "generate_features_llm",
        lambda goal: [{"name": "Trig functions", "impact": "high"}],
    )
    artifacts_written = []
    monkeypatch.setattr(
        module,
        "write_agent_artifact",
        lambda *a, **k: artifacts_written.append((a, k)) or {"artifact_id": "art-pm"},
    )
    submitted = []
    monkeypatch.setattr(module, "submit", lambda msg: submitted.append(msg))

    agent = module.PMAgent(name="PM")
    agent.handle_manager_intervention(sample_manager_intervention())

    assert len(artifacts_written) == 1
    _, kwargs = artifacts_written[0]
    assert kwargs["source_task_type"] == "MANAGER_INTERVENTION"
    assert "Build a scientific calculator." in kwargs["body"]
    assert "Trig functions" in kwargs["body"]

    assert len(submitted) == 1
    response = submitted[0]
    assert response.recipient == "MANAGER"
    assert response.task_type == "FEATURE_RESPONSE"


def test_pm_manager_intervention_without_instruction_raises_cleanly(monkeypatch):
    module = load_pm_module()
    agent = module.PMAgent(name="PM")
    message = sample_manager_intervention()
    message["payload"] = {}

    try:
        agent.handle_manager_intervention(message)
        raised = False
    except ValueError as exc:
        raised = True
        assert "instruction" in str(exc)

    assert raised


def test_pm_process_dispatches_manager_intervention(monkeypatch):
    module = load_pm_module()
    agent = module.PMAgent(name="PM")
    with mock.patch.object(agent, "handle_manager_intervention") as handler:
        with mock.patch.object(module, "ack") as ack_mock:
            agent._process(sample_manager_intervention(), use_router=True)

    handler.assert_called_once()
    ack_mock.assert_called_once()
