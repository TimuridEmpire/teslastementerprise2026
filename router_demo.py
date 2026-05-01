"""Local demo helpers for enterprise_router-connected agents.

Run this after starting the UI-Team router API. It seeds CEO, HR, and MANAGER,
prints API keys, and can send a CEO -> HR message through the shared router.
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict

import requests  # pyright: ignore[reportMissingModuleSource]

from enterprise_router_client import EnterpriseRouterClient
from message_schema import Message


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_ADMIN_SECRET = "dev-admin-secret"


def admin_headers(admin_secret: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Admin-Secret": admin_secret,
    }


def post_admin(
    base_url: str,
    path: str,
    body: Dict[str, Any],
    *,
    admin_secret: str,
) -> Dict[str, Any]:
    response = requests.post(
        f"{base_url.rstrip('/')}{path}",
        json=body,
        headers=admin_headers(admin_secret),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object from {path}.")
    return data


def register_agent(
    base_url: str,
    *,
    admin_secret: str,
    agent_name: str,
    role: str,
    hierarchy_level: int,
    trust_level: int,
    allowed_task_types: list[str] | None = None,
) -> Dict[str, Any]:
    return post_admin(
        base_url,
        "/agents",
        {
            "agent_name": agent_name,
            "role": role,
            "hierarchy_level": hierarchy_level,
            "trust_level": trust_level,
            "allowed_task_types": allowed_task_types or [],
            "issue_api_key": True,
        },
        admin_secret=admin_secret,
    )


def seed_agents(base_url: str, admin_secret: str) -> Dict[str, str]:
    agents = [
        ("CEO", "CEO", 1, 100, ["TALENT_REALLOCATION", "MINT_TOKENS", "CEO_PING"]),
        ("HR", "HR", 2, 70, ["TALENT_REALLOCATION"]),
        ("MANAGER", "MANAGER", 2, 95, []),
    ]
    keys: Dict[str, str] = {}
    for agent_name, role, level, trust, task_types in agents:
        result = register_agent(
            base_url,
            admin_secret=admin_secret,
            agent_name=agent_name,
            role=role,
            hierarchy_level=level,
            trust_level=trust,
            allowed_task_types=task_types,
        )
        api_key = result.get("api_key")
        if isinstance(api_key, str):
            keys[agent_name] = api_key
    return keys


def send_ceo_to_hr(base_url: str, ceo_key: str) -> str:
    client = EnterpriseRouterClient(
        base_url=base_url,
        agent_name="CEO",
        api_key=ceo_key,
    )
    message = Message.create(
        sender="CEO",
        recipient="HR",
        task_type="TALENT_REALLOCATION",
        context={"source": "router_demo"},
        payload={"task": "Hire 2 engineering agents and report timeline."},
    ).to_dict()
    return client.submit_envelope(
        message,
        routing_hints={
            "urgency": "high",
            "provenance_source": "router_demo",
            "provenance_agent": "CEO",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed and exercise enterprise_router demo agents.")
    parser.add_argument("--base-url", default=os.getenv("ENTERPRISE_ROUTER_API_URL", DEFAULT_BASE_URL))
    parser.add_argument("--admin-secret", default=os.getenv("ROUTER_ADMIN_SECRET", DEFAULT_ADMIN_SECRET))
    parser.add_argument("--send-ceo-to-hr", action="store_true")
    args = parser.parse_args()

    keys = seed_agents(args.base_url, args.admin_secret)
    print("Seeded agents. Store these for local terminals:")
    for name, key in keys.items():
        print(f"{name}_AGENT_API_KEY={key}")

    if args.send_ceo_to_hr:
        ceo_key = keys.get("CEO")
        if not ceo_key:
            raise RuntimeError("CEO key was not issued.")
        message_id = send_ceo_to_hr(args.base_url, ceo_key)
        print(f"Queued CEO -> HR message: {message_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
