"""Poll the Enterprise Router for inbound agent prompts (JSON envelopes).

Run after the router API is up and the agent has an API key (see
``scripts/bootstrap_router_agents.py``). Each leased message prints one JSON line
with prompt fields, then invokes the agent handler and acks/nacks the message.

Examples:
  set ENTERPRISE_ROUTER_URL=http://127.0.0.1:8765
  set CEO_AGENT_API_KEY=...
  python scripts/poll_router_prompts.py --agent CEO

  python scripts/poll_router_prompts.py --agent HR --poll-interval 1.5
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent_transport import require_router_configured
from enterprise_router.agent_artifacts import poll_router_prompts_loop
from enterprise_router_client import EnterpriseRouterClient


def _build_handler(agent_name: str):
    if agent_name == "CEO":
        from agents.ceo_agent import CeoAgent
        from ceo_distribution_tokens import CeoDistributionTokenRegistry

        agent = CeoAgent(
            name="CEO",
            distribution_registry=CeoDistributionTokenRegistry(executive_name="CEO"),
        )
        return agent.on_bus_envelope

    if agent_name == "Strategic Advisor":
        from agents.advisor_agent import AdvisorAgent

        return AdvisorAgent(name="Strategic Advisor").on_bus_envelope

    if agent_name == "HR":
        import runpy

        hr_module = runpy.run_path(str(_ROOT / "hr-agents" / "hr_agent.py"))
        supervisor = hr_module["callSupervisor"]
        return lambda envelope: supervisor(envelope)

    raise SystemExit(
        f"No poll handler wired for agent {agent_name!r}. "
        "Supported: CEO, Strategic Advisor, HR."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Poll enterprise_router for JSON prompt envelopes."
    )
    parser.add_argument(
        "--agent",
        default=os.getenv("ENTERPRISE_AGENT_NAME", "CEO"),
        help="Router recipient / agent id (default: CEO or ENTERPRISE_AGENT_NAME).",
    )
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--once", action="store_true", help="Process at most one message then exit.")
    parser.add_argument(
        "--quiet-prompt-log",
        action="store_true",
        help="Do not print envelope_prompt_json lines to stdout.",
    )
    args = parser.parse_args()

    agent_name = (args.agent or "").strip()
    if not agent_name:
        raise SystemExit("--agent is required.")

    os.environ["ENTERPRISE_AGENT_NAME"] = agent_name
    require_router_configured(agent_name)

    client = EnterpriseRouterClient.from_env(agent_name=agent_name)
    handler = _build_handler(agent_name)

    print(
        f"[{agent_name}] polling enterprise_router at {client.base_url} "
        f"every {args.poll_interval:g}s",
        flush=True,
    )

    poll_router_prompts_loop(
        recipient=agent_name,
        fetch_next=client.fetch_next,
        ack=client.ack_message,
        nack=client.nack_message,
        handler=handler,
        poll_interval_s=args.poll_interval,
        log_prompt_json=not args.quiet_prompt_log,
        once=args.once,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
