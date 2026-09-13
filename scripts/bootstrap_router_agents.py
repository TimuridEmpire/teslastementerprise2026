"""
Register default department agents on a running enterprise router (admin API).

Usage:
  set ENTERPRISE_ROUTER_ADMIN_SECRET=your-admin-secret
  python scripts/bootstrap_router_agents.py
"""

from __future__ import annotations

import os
import sys

import requests  # pyright: ignore[reportMissingModuleSource]

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from enterprise_router.config import RouterSettings

AGENTS = [
    ("CEO", "executive", 100, 100, ["CEO_PING", "CEO_CHAT", "CEO_REASONING_LOOP", "CEO_METRICS", "PM_REPORT", "ARTIFACT_PUBLISHED", "AGENT_ARTIFACT_READY", "MINT_TOKENS", "BUDGET_APPROVAL", "MANAGER_INTERVENTION", "IMPLEMENT_FEATURE", "STRATEGY_REVIEW_RESULT"]),
    ("PM", "product", 80, 80, ["DEFINE_Q2_ROADMAP", "REQUEST_FEATURES", "CEO_STRATEGY_DIRECTIVE", "FEATURE_RESPONSE", "MANAGER_INTERVENTION"]),
    ("Marketing", "marketing", 70, 70, ["LAUNCH_CAMPAIGN", "PM_REPORT", "THREAD_ALLOCATION", "MANAGER_INTERVENTION"]),
    ("HR", "hr", 60, 60, ["TALENT_REALLOCATION", "THREAD_ALLOCATION", "MANAGER_INTERVENTION"]),
    ("Engineering", "engineering", 70, 70, ["IMPLEMENT_FEATURE", "FEATURE_RESPONSE", "THREAD_ALLOCATION", "MANAGER_INTERVENTION"]),
    ("Sales", "sales", 60, 60, ["CAMPAIGN_LAUNCHED", "MANAGER_INTERVENTION"]),
    ("Finance", "finance", 60, 60, ["BUDGET_APPROVAL", "MANAGER_INTERVENTION"]),
    ("MANAGER", "manager", 90, 90, ["AGENT_ARTIFACT_READY", "PM_REPORT", "FEATURE_RESPONSE", "ARTIFACT_PUBLISHED"]),
    ("Strategic Advisor", "advisor", 85, 85, ["STRATEGY_REVIEW_REQUEST", "CEO_PROPOSAL_FOR_REVIEW", "MANAGER_INTERVENTION"]),
]

# One distinct env var name per agent's issued key. Consumed by:
#  - website/app/api/router/[...path]/route.ts (the server-side proxy that
#    holds every credential -- see the Enterprise Deployment Blueprint's
#    critical-path finding on why these must NOT be NEXT_PUBLIC_* anymore)
#  - docker-compose.yml's worker-* services (remapped to the single generic
#    ENTERPRISE_AGENT_API_KEY each run_single_agent.py process reads)
#  - setup_local_runtime.py's generated key files
AGENT_ENV_NAMES = {
    "CEO": "CEO_AGENT_API_KEY",
    "PM": "PM_AGENT_API_KEY",
    "Marketing": "MARKETING_AGENT_API_KEY",
    "HR": "HR_AGENT_API_KEY",
    "Engineering": "ENGINEERING_AGENT_API_KEY",
    "Sales": "SALES_AGENT_API_KEY",
    "Finance": "FINANCE_AGENT_API_KEY",
    "MANAGER": "MANAGER_AGENT_API_KEY",
    "Strategic Advisor": "ADVISOR_AGENT_API_KEY",
}


def main() -> int:
    settings = RouterSettings.from_env()
    base = (
        os.getenv("ENTERPRISE_ROUTER_URL")
        or os.getenv("ENTERPRISE_ROUTER_API_URL")
        or f"http://{settings.api_host}:{settings.api_port}"
    ).rstrip("/")
    admin = settings.admin_secret
    headers = {"X-Admin-Secret": admin, "Content-Type": "application/json"}

    issued_keys = {}
    for name, role, hierarchy, trust, allowed_task_types in AGENTS:
        resp = requests.post(
            f"{base}/agents",
            headers=headers,
            json={
                "agent_name": name,
                "role": role,
                "hierarchy_level": hierarchy,
                "trust_level": trust,
                "allowed_task_types": allowed_task_types,
                "issue_api_key": True,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        key = data.get("api_key", "")
        if key:
            issued_keys[name] = key
        print(f"{name}: registered" + (f", api_key={key}" if key else ""))

    # Website server env values -- these belong in the website process's own
    # environment (or a Docker Compose .env), never NEXT_PUBLIC_*: the
    # server-side proxy at app/api/router/[...path]/route.ts is the only
    # thing that reads them, and the browser never sees them.
    print("\nWebsite server env values (website process env, or repo-root .env for Docker Compose):")
    print(f"ROUTER_URL={base}")
    print("ENTERPRISE_ROUTER_ADMIN_SECRET=<already set -- same value used to run this script>")
    for name, key in issued_keys.items():
        env_name = AGENT_ENV_NAMES.get(name)
        if env_name:
            print(f"{env_name}={key}")

    # run_single_agent.py reads one generic ENTERPRISE_AGENT_API_KEY, not a
    # per-agent-named var -- set it to whichever agent's key you're
    # starting that process as.
    print("\nAgent runner env values (set ENTERPRISE_AGENT_API_KEY per process, to that agent's key):")
    print(f"ENTERPRISE_ROUTER_URL={base}")
    for name, key in issued_keys.items():
        print(f"  {name}: ENTERPRISE_AGENT_API_KEY={key}")
    print("\nThen run: python run_agents.py --agents all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
