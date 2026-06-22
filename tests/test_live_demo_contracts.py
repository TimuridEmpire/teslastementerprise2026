from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from finance_schema import AgentMessage
from message_schema import envelope_dict
from finance_token_manager import FinanceTokenManager, STANDARD_SCENARIO


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeRouterClient:
    def __init__(self):
        self.submitted = []

    def submit_message(self, envelope):
        self.submitted.append(envelope)
        return {"ok": True}


def allowed_tasks_for(agent_name: str) -> set[str]:
    from scripts.bootstrap_router_agents import AGENTS

    for name, _role, _hierarchy, _trust, allowed in AGENTS:
        if name == agent_name:
            return set(allowed)
    raise AssertionError(f"No bootstrap registration found for {agent_name}")


def test_bootstrap_allows_partial_demo_message_chain():
    assert {"CEO_REASONING_LOOP", "STRATEGY_REVIEW_RESULT", "TOKEN_TOPUP_NOTIFICATION"} <= allowed_tasks_for("CEO")
    assert {"CEO_STRATEGY_DIRECTIVE", "FEATURE_RESPONSE"} <= allowed_tasks_for("PM")
    assert {"IMPLEMENT_FEATURE", "THREAD_ALLOCATION"} <= allowed_tasks_for("Engineering")
    assert {"TALENT_REALLOCATION", "THREAD_ALLOCATION"} <= allowed_tasks_for("HR")
    assert {"LAUNCH_CAMPAIGN", "PM_REPORT", "THREAD_ALLOCATION"} <= allowed_tasks_for("Marketing")
    assert {"CAMPAIGN_LAUNCHED", "QUALIFY_LEAD", "CLOSE_DEAL", "PIPELINE_REPORT"} <= allowed_tasks_for("Sales")
    assert {"REVENUE_LOG", "TOKEN_TOPUP_REQUEST", "TOKEN_BALANCE_QUERY"} <= allowed_tasks_for("Finance")


def test_runner_marks_sales_and_finance_as_implemented():
    import run_agents
    import run_single_agent

    assert run_agents.AGENTS["sales"].implemented is True
    assert run_agents.AGENTS["finance"].implemented is True
    assert run_single_agent.canonical_agent_name("sales") == "Sales"
    assert run_single_agent.canonical_agent_name("finance") == "Finance"


def test_finance_owns_routine_token_topups_and_notifies_ceo():
    router = FakeRouterClient()
    manager = FinanceTokenManager(router_client=router)
    manager.initialize_registry()

    result = manager.handle_topup_request(
        agent_name="PM",
        scenario_id=STANDARD_SCENARIO,
        requested_amount=4,
        reason="unit test",
    )

    assert result["status"] == "approved"
    assert result["ceo_notified"] is True
    assert router.submitted
    notification = envelope_dict(router.submitted[-1])
    assert notification["sender"] == "Finance"
    assert notification["recipient"] == "CEO"
    assert notification["task_type"] == "TOKEN_TOPUP_NOTIFICATION"

    registry = manager.registry
    try:
        registry.mint(STANDARD_SCENARIO, quantity=1, holder="PM", acting_executive="CEO")
    except PermissionError:
        pass
    else:
        raise AssertionError("CEO should not mint routine Finance-owned operating tokens")


def test_finance_token_balance_query_writes_artifact(monkeypatch):
    module = load_module("finance_agent_under_test", "finance-agents/finance_agent.py")
    artifacts = []
    monkeypatch.setattr(module, "write_agent_artifact", lambda agent_name, **kwargs: artifacts.append((agent_name, kwargs)) or {"artifact_id": "art-fin"})

    agent = module.FinanceAgent(router_client=FakeRouterClient())
    agent.startup()
    msg = AgentMessage(
        sender="PM",
        recipient="Finance",
        task_type="TOKEN_BALANCE_QUERY",
        payload={"scenario_id": STANDARD_SCENARIO},
    )

    reply = asyncio.run(agent._handle_token_balance_query(msg))

    assert reply.status == "done"
    assert reply.payload["agent"] == "PM"
    assert artifacts
    assert artifacts[0][0] == "Finance"
    assert artifacts[0][1]["artifact_type"] == "token_balance"


def test_sales_campaign_launch_writes_artifact(monkeypatch):
    module = load_module("sales_agent_under_test", "sales-agents/sales_agent.py")
    artifacts = []
    monkeypatch.setattr(module, "write_agent_artifact", lambda agent_name, **kwargs: artifacts.append((agent_name, kwargs)) or {"artifact_id": "art-sales"})

    agent = module.SalesAgent(router_client=FakeRouterClient())
    msg = AgentMessage(
        sender="Marketing",
        recipient="Sales",
        task_type="CAMPAIGN_LAUNCHED",
        payload={"product_name": "Kanosei", "expected_leads": 12},
        context={"run_id": "demo-run"},
    )

    reply = asyncio.run(agent._handle_campaign_launched(msg))

    assert reply.status == "done"
    assert reply.payload["campaign"]["product_name"] == "Kanosei"
    assert artifacts
    assert artifacts[0][0] == "Sales"
    assert artifacts[0][1]["artifact_type"] == "sales_campaign_intake"
