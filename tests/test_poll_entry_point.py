"""
main.py — Finance + Sales Agent System entry point.

Modes:
  python main.py demo          Run the 'Launch SaaS Feature' scenario (no API key needed)
  python main.py run           Async in-memory bus mode (requires OLLAMA_READY)
  python main.py status        Print current tool-layer stats
  python main.py test          Run unit tests
"""

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║   Finance + Sales Agent System                           ║
╚══════════════════════════════════════════════════════════╝
""")


# ---------------------------------------------------------------------------
# Demo mode — no API key needed
# ---------------------------------------------------------------------------

async def run_demo():
    from bus.message_bus import bus
    from finance_schema import AgentMessage
    from tools.finance_tools import (
        get_budget_status, generate_pl_report, monte_carlo_forecast, log_revenue
    )
    from tools.sales_tools import (
        qualify_lead, generate_pitch, close_deal, get_pipeline_report
    )

    print_banner()
    print("=== DEMO: Launch SaaS Feature Scenario ===\n")

    print("── Step 1: CEO checks Q2 budget ──")
    print(json.dumps(get_budget_status("Q2-2026"), indent=2))

    print("\n── Step 2: Finance runs Monte Carlo forecast ──")
    print(json.dumps(monte_carlo_forecast(55000, 42000, months=6, simulations=500), indent=2))

    print("\n── Step 3: Sales qualifies leads ──")
    for lead_id in ["lead-001", "lead-003", "lead-004"]:
        q = qualify_lead(lead_id)
        print(f"  {lead_id} ({q['company']}): score={q['score']} → {'QUALIFIED' if q['qualified'] else 'Not qualified'}")

    print("\n── Step 4: Sales generates pitch for AcmeCorp ──")
    print(generate_pitch("lead-001")["pitch"])

    print("\n── Step 5: Sales closes deal with MidCo Industries ──")
    deal = close_deal("lead-003", 18000.0, won=True)
    print(json.dumps(deal, indent=2))

    print("\n── Step 6: Finance logs revenue from closed deal ──")
    print(json.dumps(log_revenue(18000.0, deal.get("deal_id", "deal-demo"), "MidCo Industries"), indent=2))

    print("\n── Step 7: Finance generates P&L report ──")
    print(json.dumps(generate_pl_report("Q2-2026"), indent=2))

    print("\n── Step 8: Sales pipeline summary ──")
    print(json.dumps(get_pipeline_report(), indent=2))

    print("\n── Step 9: Session token stats ──")
    print(json.dumps(bus.get_session_stats(), indent=2))

    print("\nDemo complete.\n")


# ---------------------------------------------------------------------------
# Live async mode
# ---------------------------------------------------------------------------

async def run_live():
    api_key = True
    if False:
        print("ERROR: OLLAMA_READY not set. Use 'python main.py demo' for stub mode.")
        sys.exit(1)

    from bus.message_bus import bus
    from agents.finance_agent import FinanceAgent
    from agents.sales_agent import SalesAgent
    from finance_finance_schema import AgentMessage

    print_banner()
    print("Starting live agent loop...\n")

    finance = FinanceAgent(bus)
    sales   = SalesAgent(bus)

    async def seed_tasks():
        await asyncio.sleep(0.1)
        tasks = [
            AgentMessage(task_type="GENERATE_PL_REPORT", sender="CEO", recipient="FINANCE",
                         payload={"period": "Q2-2026"}),
            AgentMessage(task_type="QUALIFY_LEAD", sender="CEO", recipient="SALES",
                         payload={"lead_id": "lead-001"}),
            AgentMessage(task_type="PIPELINE_REPORT", sender="CEO", recipient="SALES", payload={}),
            AgentMessage(task_type="CASH_FLOW_FORECAST", sender="CEO", recipient="FINANCE",
                         payload={"base_monthly_revenue_usd": 55000, "base_monthly_expense_usd": 42000}),
        ]
        for t in tasks:
            await bus.send(t.to_dict())
        logger.info("Seeded 4 initial tasks")

    await asyncio.gather(seed_tasks(), finance.run(max_cycles=20), sales.run(max_cycles=20))

    bus.dump_log("logs/session_log.json")
    print("\nFinal Stats:")
    print(json.dumps(finance.get_status(), indent=2))
    print(json.dumps(sales.get_status(), indent=2))
    print(json.dumps(bus.get_session_stats(), indent=2))


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if mode == "demo":
        asyncio.run(run_demo())
    elif mode == "run":
        asyncio.run(run_live())
    elif mode == "status":
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "finance-agents"))
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sales-agents"))
        from finance_tools import get_budget_status, generate_pl_report
        from sales_tools import get_pipeline_report
        print_banner()
        print(json.dumps(get_budget_status("Q2-2026"), indent=2))
        print(json.dumps(generate_pl_report("Q2-2026"), indent=2))
        print(json.dumps(get_pipeline_report(), indent=2))
    elif mode == "test":
        import subprocess
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                           cwd=os.path.dirname(__file__))
        sys.exit(r.returncode)
    else:
        print(f"Unknown mode: {mode}. Use: demo | run | status | test")