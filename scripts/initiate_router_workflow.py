"""Seed a router-driven workflow that makes agents communicate.

Run this after:
  1. The Enterprise Router API is running.
  2. scripts/bootstrap_router_agents.py has issued API keys.
  3. Optional: run_agents.py is running, so workers immediately process messages.

Required env:
  ENTERPRISE_ROUTER_URL
  CEO_AGENT_API_KEY

Optional env:
  INITIATION_RUN_ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from enterprise_router_client import EnterpriseRouterClient
from message_schema import Message

DEFAULT_BASE_URL = "http://localhost:8000"


@dataclass(frozen=True)
class SeedMessage:
    recipient: str
    task_type: str
    urgency: str
    payload: dict[str, Any]


def run_id_from_env() -> str:
    return os.getenv("INITIATION_RUN_ID", "").strip() or f"init-{uuid.uuid4().hex[:8]}"


def base_context(*, run_id: str, scenario: str, recipient: str, task_type: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "scenario": scenario,
        "initiated_by": "scripts/initiate_router_workflow.py",
        "provenance_source": "initiation_script",
        "provenance_agent": "CEO",
        "recipient": recipient,
        "task_type": task_type,
    }


def routing_hints(*, run_id: str, scenario: str, seed: SeedMessage) -> dict[str, Any]:
    dedupe_key = f"{run_id}:{scenario}:{seed.recipient}:{seed.task_type}"
    return {
        "urgency": seed.urgency,
        "dedupe_key": dedupe_key,
        "provenance_source": "initiation_script",
        "provenance_agent": "CEO",
    }


def build_seed_messages(args: argparse.Namespace) -> list[SeedMessage]:
    seeds = [
        SeedMessage(
            recipient="PM",
            task_type="DEFINE_Q2_ROADMAP",
            urgency="critical",
            payload={
                "product_name": "Enterprise Router Console",
                "business_goal": "Create a live operations console that shows agent routing, queue health, and workflow progress.",
                "description": "Plan the first product roadmap for router-backed multi-agent operations.",
            },
        ),
    ]

    if args.include_engineering:
        seeds.append(
            SeedMessage(
                recipient="Engineering",
                task_type="IMPLEMENT_FEATURE",
                urgency="high",
                payload={
                    "feature_id": "router-live-metrics",
                    "feature_name": "Router-derived visualization metrics",
                    "acceptance_criteria": [
                        "Derive chart data from router audit events.",
                        "Preserve mock fallbacks when the router is offline.",
                        "Expose queue state and priority distributions without direct database reads.",
                    ],
                },
            )
        )

    if args.include_hr:
        seeds.append(
            SeedMessage(
                recipient="HR",
                task_type="TALENT_REALLOCATION",
                urgency="normal",
                payload={
                    "task": "Assess staffing for PM, Engineering, and Marketing workers during the startup demo.",
                    "requested_roles": ["Product Operator", "Router Observability Engineer", "Campaign Coordinator"],
                },
            )
        )

    if args.include_advisor:
        seeds.append(
            SeedMessage(
                recipient="Strategic Advisor",
                task_type="STRATEGY_REVIEW_REQUEST",
                urgency="high",
                payload={
                    "proposal": "Start a router-driven demo workflow that coordinates PM, Engineering, HR, and Marketing.",
                    "success_criteria": [
                        "Messages are routed only through the Enterprise Router.",
                        "Audit and queue visualizations update from live router data.",
                        "Workers can ack or nack all seeded messages.",
                    ],
                },
            )
        )

    return seeds


def submit_seed(client: EnterpriseRouterClient, *, seed: SeedMessage, run_id: str, scenario: str) -> dict[str, Any]:
    context = base_context(
        run_id=run_id,
        scenario=scenario,
        recipient=seed.recipient,
        task_type=seed.task_type,
    )
    envelope = Message.create(
        sender="CEO",
        recipient=seed.recipient,
        task_type=seed.task_type,
        context=context,
        payload=seed.payload,
    ).to_dict()
    hints = routing_hints(run_id=run_id, scenario=scenario, seed=seed)
    message_id = client.submit_envelope(envelope, routing_hints=hints)
    return {
        "message_id": message_id,
        "recipient": seed.recipient,
        "task_type": seed.task_type,
        "urgency": seed.urgency,
        "dedupe_key": hints["dedupe_key"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a router-driven multi-agent workflow.")
    parser.add_argument("--scenario", default="startup-demo")
    parser.add_argument("--dry-run", action="store_true", help="Print planned messages without submitting them.")
    parser.add_argument("--include-engineering", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-hr", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-advisor", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    base_url = os.getenv("ENTERPRISE_ROUTER_URL", os.getenv("ENTERPRISE_ROUTER_API_URL", DEFAULT_BASE_URL)).strip()
    ceo_key = os.getenv("CEO_AGENT_API_KEY", os.getenv("NEXT_PUBLIC_CEO_API_KEY", "")).strip()
    if not ceo_key and not args.dry_run:
        raise SystemExit("CEO_AGENT_API_KEY is required unless --dry-run is used.")

    run_id = run_id_from_env()
    seeds = build_seed_messages(args)
    preview = [
        {
            "sender": "CEO",
            "recipient": seed.recipient,
            "task_type": seed.task_type,
            "urgency": seed.urgency,
            "run_id": run_id,
            "scenario": args.scenario,
            "dedupe_key": routing_hints(run_id=run_id, scenario=args.scenario, seed=seed)["dedupe_key"],
        }
        for seed in seeds
    ]

    if args.dry_run:
        print(json.dumps({"dry_run": True, "messages": preview}, indent=2))
        return 0

    client = EnterpriseRouterClient(base_url=base_url, agent_name="CEO", api_key=ceo_key)
    submitted = [submit_seed(client, seed=seed, run_id=run_id, scenario=args.scenario) for seed in seeds]
    print(json.dumps({"run_id": run_id, "scenario": args.scenario, "submitted": submitted}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
