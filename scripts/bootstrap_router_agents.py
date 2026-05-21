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
    ("CEO", "executive", 100, 100),
    ("PM", "product", 80, 80),
    ("Marketing", "marketing", 70, 70),
    ("HR", "hr", 60, 60),
    ("Engineering", "engineering", 70, 70),
    ("Sales", "sales", 60, 60),
    ("Finance", "finance", 60, 60),
    ("MANAGER", "manager", 90, 90),
    ("Strategic Advisor", "advisor", 85, 85),
]


def main() -> int:
    settings = RouterSettings.from_env()
    base = f"http://{settings.api_host}:{settings.api_port}"
    admin = settings.admin_secret
    headers = {"X-Admin-Secret": admin, "Content-Type": "application/json"}

    for name, role, hierarchy, trust in AGENTS:
        resp = requests.post(
            f"{base}/agents",
            headers=headers,
            json={
                "agent_name": name,
                "role": role,
                "hierarchy_level": hierarchy,
                "trust_level": trust,
                "issue_api_key": True,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        key = data.get("api_key", "")
        print(f"{name}: registered, api_key={key[:12]}..." if key else f"{name}: registered")

    print("\nSet per-process env, e.g. for HR:")
    print("  ENTERPRISE_ROUTER_URL=http://127.0.0.1:8765")
    print("  ENTERPRISE_AGENT_NAME=HR")
    print("  ENTERPRISE_AGENT_API_KEY=<key printed above>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
