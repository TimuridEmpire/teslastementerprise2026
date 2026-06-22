"""Run one Enterprise Router-backed agent as a polling worker.

This file wraps the agents that do not already have their own long-running
entrypoint. It expects the caller to provide:

  ENTERPRISE_ROUTER_URL
  ENTERPRISE_AGENT_NAME
  ENTERPRISE_AGENT_API_KEY

Use run_agents.py to start several workers at once.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import runpy
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Callable

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_transport import require_router_configured
from ceo_distribution_tokens import CeoDistributionTokenRegistry

CANONICAL_NAMES = {
    "ceo": "CEO",
    "pm": "PM",
    "product": "PM",
    "marketing": "Marketing",
    "hr": "HR",
    "engineering": "Engineering",
    "eng": "Engineering",
    "advisor": "Strategic Advisor",
    "strategic-advisor": "Strategic Advisor",
    "strategic_advisor": "Strategic Advisor",
    "sales": "Sales",
    "finance": "Finance",
}


def canonical_agent_name(value: str) -> str:
    key = value.strip().lower().replace(" ", "-")
    if key not in CANONICAL_NAMES:
        known = ", ".join(sorted(set(CANONICAL_NAMES.values())))
        raise SystemExit(f"Unknown runnable agent {value!r}. Known workers: {known}")
    return CANONICAL_NAMES[key]


def load_module(module_name: str, path: Path) -> ModuleType:
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_drain_agent(agent_name: str, factory: Callable[[], object], interval: float) -> None:
    agent = factory()
    print(f"[{agent_name}] worker started; polling every {interval:g}s", flush=True)
    while True:
        run = getattr(agent, "run")
        run()
        time.sleep(interval)


def run_ceo(interval: float) -> None:
    from agents.ceo_agent import CeoAgent

    agent = CeoAgent(
        name="CEO",
        distribution_registry=CeoDistributionTokenRegistry(executive_name="CEO"),
    )
    print(f"[CEO] worker started; polling every {interval:g}s", flush=True)
    while True:
        processed = agent.process_one_router_message(recipient="CEO")
        if not processed:
            time.sleep(interval)


def run_advisor(interval: float) -> None:
    from agents.advisor_agent import AdvisorAgent

    agent = AdvisorAgent(name="Strategic Advisor")
    print(f"[Strategic Advisor] worker started; polling every {interval:g}s", flush=True)
    while True:
        processed = agent.process_one_router_message(recipient="Strategic Advisor")
        if not processed:
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Enterprise Router-backed agent worker.")
    parser.add_argument("agent", help="One of: CEO, PM, Marketing, HR, Engineering, Advisor, Sales, Finance")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()

    agent_name = canonical_agent_name(args.agent)
    os.environ["ENTERPRISE_AGENT_NAME"] = agent_name
    require_router_configured(agent_name)

    if agent_name == "HR":
        runpy.run_path(str(ROOT / "hr-agents" / "hr_agent.py"), run_name="__main__")
        return 0

    if agent_name == "Engineering":
        runpy.run_path(str(ROOT / "eng-agents" / "engineering_agent.py"), run_name="__main__")
        return 0

    if agent_name == "PM":
        module = load_module("pm_worker_module", ROOT / "pm-agents" / "pm_agent.py")
        run_drain_agent("PM", lambda: module.PMAgent(name="PM"), args.poll_interval)
        return 0

    if agent_name == "Marketing":
        module = load_module("marketing_worker_module", ROOT / "marketing-agents" / "marketing_agent.py")
        run_drain_agent("Marketing", lambda: module.MarketingAgent(name="Marketing"), args.poll_interval)
        return 0

    if agent_name == "CEO":
        run_ceo(args.poll_interval)
        return 0

    if agent_name == "Strategic Advisor":
        run_advisor(args.poll_interval)
        return 0

    if agent_name == "Finance":
        runpy.run_path(str(ROOT / "finance-agents" / "finance_agent.py"), run_name="__main__")
        return 0

    if agent_name == "Sales":
        runpy.run_path(str(ROOT / "sales-agents" / "sales_agent.py"), run_name="__main__")
        return 0

    raise SystemExit(f"No worker is implemented for {agent_name}.")


if __name__ == "__main__":
    raise SystemExit(main())
