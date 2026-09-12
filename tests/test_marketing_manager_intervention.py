"""
Regression tests: the website Chat page's `/mkt <request>` command sends
task_type MANAGER_INTERVENTION (Marketing is registered to accept it — see
scripts/bootstrap_router_agents.py) but marketing_agent.py's dispatch had no
case for it, so it fell through to "unhandled task_type" and was silently
acked with no visible effect.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import mock


def load_marketing_module():
    path = Path(__file__).resolve().parents[1] / "marketing-agents" / "marketing_agent.py"
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("marketing_agent_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_manager_intervention(instruction: str = "Launch a Q4 retention campaign.") -> dict:
    """Shape sent by website/components/chat/CommandChat.tsx's `/mkt <text>`
    command: POST /manager/interventions -> EnterpriseRouter.
    submit_manager_intervention() always folds the free-text instruction
    into payload["instruction"]."""
    return {
        "id": "mkt-msg-1",
        "timestamp": "2026-05-26T00:00:00Z",
        "sender": "MANAGER",
        "recipient": "Marketing",
        "task_type": "MANAGER_INTERVENTION",
        "context": {"source": "command_chat"},
        "payload": {"instruction": instruction},
        "status": "pending",
        "error": "",
    }


def test_marketing_handles_manager_intervention_from_chat_mkt_command(monkeypatch):
    module = load_marketing_module()
    monkeypatch.setattr(
        module,
        "plan_campaign",
        lambda product, features: {
            "product": product, "features": features, "tagline": "t",
            "channel": "Email", "budget": 4000, "expected_leads": 50, "timeline_weeks": 4,
        },
    )
    monkeypatch.setattr(module, "save_campaign", lambda campaign: None)
    monkeypatch.setattr(module, "generate_email", lambda **k: {"subject": "s", "body": "b"})
    monkeypatch.setattr(module, "generate_image_prompt", lambda **k: {"prompt": "p"})
    monkeypatch.setattr(
        module, "write_artifact", lambda **k: {"path": "/tmp/brief.md"}
    )
    monkeypatch.setattr(module, "publish_artifact", lambda *a, **k: None)
    artifacts_written = []
    monkeypatch.setattr(
        module,
        "write_agent_artifact",
        lambda *a, **k: artifacts_written.append((a, k)) or {"artifact_id": "art-mkt"},
    )
    submitted = []
    monkeypatch.setattr(module, "submit", lambda msg: submitted.append(msg))

    agent = module.MarketingAgent(name="Marketing")
    agent.handle_manager_intervention(sample_manager_intervention())

    assert len(artifacts_written) == 1
    _, kwargs = artifacts_written[0]
    assert kwargs["source_task_type"] == "MANAGER_INTERVENTION"

    # Under the $10k threshold -> CAMPAIGN_LAUNCHED sent to Sales, not a
    # budget approval request to CEO.
    assert len(submitted) == 1
    assert submitted[0].task_type == "CAMPAIGN_LAUNCHED"
    assert submitted[0].recipient == "Sales"


def test_marketing_manager_intervention_without_instruction_raises_cleanly():
    module = load_marketing_module()
    agent = module.MarketingAgent(name="Marketing")
    message = sample_manager_intervention()
    message["payload"] = {}

    try:
        agent.handle_manager_intervention(message)
        raised = False
    except ValueError as exc:
        raised = True
        assert "instruction" in str(exc)

    assert raised


def test_marketing_process_dispatches_manager_intervention():
    module = load_marketing_module()
    agent = module.MarketingAgent(name="Marketing")
    with mock.patch.object(agent, "handle_manager_intervention") as handler:
        with mock.patch.object(module, "ack") as ack_mock:
            agent._process(sample_manager_intervention(), use_router=True)

    handler.assert_called_once()
    ack_mock.assert_called_once()
