"""
finance-agents/finance_agent.py — Finance Agent (Router-integrated)

Responsibilities:
  - Budget allocation and tracking
  - Invoice tracking / P&L generation
  - Monte Carlo cash flow forecasting
  - Burn-rate alerts (escalates >$10K to CEO)
  - Revenue logging from Sales Agent
  - Token cost logging per call
  - Creates and distributes distribution tokens to all agents (CFO authority)
  - Handles token top-up requests from agents that have run out
  - Notifies CEO (FYI) of all token decisions
"""

from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from enterprise_router_client import EnterpriseRouterClient
from finance_token_manager import FinanceTokenManager, STANDARD_SCENARIO, BROADCAST_SCENARIO
from finance_tools import (
    allocate_budget,
    generate_audit_report,
    generate_pl_report,
    get_budget_status,
    log_expense,
    log_revenue,
    log_token_cost,
    monte_carlo_forecast,
)
from llm_provider import llm_json_object
from message_schema import Message

logger = logging.getLogger("finance_agent")

CEO_APPROVAL_THRESHOLD_USD = 10_000

FINANCE_SYSTEM_PROMPT = """You are the Finance Agent (CFO) for an AI-simulated enterprise.

Your role:
- Oversee budgets, P&L, cash flow, and financial forecasting
- Flag burn-rate risks and escalate spend > $10,000 to the CEO
- Log all revenue received from the Sales Agent
- Run Monte Carlo simulations for probabilistic forecasting
- Produce clear, concise financial reports
- Own distribution token issuance: you mint and distribute tokens to all agents
- Approve or deny token top-up requests from agents that have run out

Decision rules:
1. Any single expense or allocation > $10,000 REQUIRES CEO approval before proceeding.
2. If projected monthly burn exceeds 80% of budget, send a BUDGET_ALERT immediately.
3. Revenue from Sales is logged immediately and reflected in P&L.
4. Token top-up approvals are YOUR authority — CEO is notified FYI only.

Always respond in JSON format matching the requested task output.
Keep responses under 900 tokens.
"""


class FinanceAgent:

    def __init__(self, router_client: EnterpriseRouterClient):
        self.client = router_client
        self.name = "Finance"
        self.token_manager = FinanceTokenManager(
            router_client=router_client,
            executive_name="CEO",
            cfo_name=self.name,
        )

    def startup(self) -> None:
        """Initialize token registry on first boot."""
        logger.info("[Finance] Initializing token registry...")
        self.token_manager.initialize_registry()
        logger.info("[Finance] Token registry ready.")

    # ─── Main poll loop ───────────────────────────────────────────────────────

    def run_once(self) -> bool:
        """Fetch and process one message. Returns True if a message was handled."""
        envelope = self.client.fetch_next(self.name)
        if not envelope:
            return False

        task = envelope.get("task_type", "")
        sender = envelope.get("sender", "")
        msg_id = envelope.get("id", "")
        logger.info("[Finance] Handling: %s from %s", task, sender)

        try:
            handlers = {
                "GENERATE_PL_REPORT":       self._handle_pl_report,
                "BUDGET_APPROVAL":          self._handle_budget_approval,
                "CASH_FLOW_FORECAST":       self._handle_forecast,
                "REVENUE_LOG":              self._handle_revenue_log,
                "AUDIT_REPORT":             self._handle_audit,
                "MONTE_CARLO_SIM":          self._handle_monte_carlo,
                "TOKEN_TOPUP_REQUEST":      self._handle_token_topup_request,
                "TOKEN_BALANCE_QUERY":      self._handle_token_balance_query,
            }
            handler = handlers.get(task)
            if handler:
                reply_payload, reply_status = handler(envelope)
            else:
                logger.warning("[Finance] Unknown task: %s", task)
                reply_payload = {"error": f"Unknown task: {task}"}
                reply_status = "error"

            self._send_reply(envelope, reply_payload, reply_status)
            self.client.ack(msg_id, self.name)

        except Exception as exc:
            logger.exception("[Finance] Error handling %s: %s", task, exc)
            self.client.nack(msg_id, reason=str(exc), recipient=self.name)

        return True

    # ─── Task handlers ────────────────────────────────────────────────────────

    def _handle_pl_report(self, envelope: dict) -> tuple:
        quarter = envelope.get("payload", {}).get("period", "Q2-2026")
        raw_pl = generate_pl_report(quarter)
        budget = get_budget_status(quarter)

        prompt = f"""Generate a concise CFO-style P&L summary for {quarter}.

Raw data:
{json.dumps(raw_pl, indent=2)}

Budget status:
{json.dumps(budget, indent=2)}

Return JSON with keys: summary (string), health (good/warning/critical),
key_risks (list of strings), recommendations (list of strings).
"""
        result = llm_json_object(prompt) or {}
        log_token_cost("Finance", "GENERATE_PL_REPORT", 0, 0, 0, 0.0)

        if budget.get("burn_pct", 0) > 75:
            self._send_budget_alert(quarter, budget)

        return {**result, "pl_data": raw_pl, "budget": budget}, "done"

    def _handle_budget_approval(self, envelope: dict) -> tuple:
        payload  = envelope.get("payload", {})
        amount   = payload.get("amount_usd", 0)
        category = payload.get("category", "general")
        quarter  = payload.get("quarter", "Q2-2026")

        if amount > CEO_APPROVAL_THRESHOLD_USD:
            # Escalate to CEO and wait (send message; for now return pending)
            self._escalate_to_ceo(envelope, amount, category)
            return {"status": "ESCALATED_TO_CEO", "amount_usd": amount}, "pending"

        result = allocate_budget(quarter, amount, category)
        return result, "done"

    def _handle_forecast(self, envelope: dict) -> tuple:
        p = envelope.get("payload", {})
        mc = monte_carlo_forecast(
            base_revenue_usd=p.get("base_monthly_revenue_usd", 50000),
            base_expense_usd=p.get("base_monthly_expense_usd", 45000),
            months=p.get("months", 6),
        )
        prompt = f"""Interpret this Monte Carlo cash flow simulation as a CFO would.

{json.dumps(mc, indent=2)}

Return JSON with: narrative (2-3 sentences), risk_level, top_actions (list of 3 short strings).
"""
        result = llm_json_object(prompt) or {}
        return {**mc, "llm_interpretation": result}, "done"

    def _handle_revenue_log(self, envelope: dict) -> tuple:
        p = envelope.get("payload", {})
        result = log_revenue(
            amount_usd=p.get("deal_value_usd", 0),
            deal_id=p.get("deal_id", ""),
            company=p.get("company", "Unknown"),
            quarter=p.get("quarter", "Q2-2026"),
        )
        return result, "done"

    def _handle_audit(self, envelope: dict) -> tuple:
        quarter = envelope.get("payload", {}).get("quarter", "Q2-2026")
        audit = generate_audit_report(quarter)
        prompt = f"""Review this audit report and flag any concerns.

{json.dumps(audit, indent=2)}

Return JSON with: findings (list), severity (low/medium/high), token_cost_summary (string).
"""
        result = llm_json_object(prompt) or {}
        return {**audit, "llm_analysis": result}, "done"

    def _handle_monte_carlo(self, envelope: dict) -> tuple:
        p = envelope.get("payload", {})
        mc = monte_carlo_forecast(
            base_revenue_usd=p.get("base_revenue_usd", 50000),
            base_expense_usd=p.get("base_expense_usd", 45000),
            months=p.get("months", 6),
            simulations=p.get("simulations", 1000),
        )
        return mc, "done"

    def _handle_token_topup_request(self, envelope: dict) -> tuple:
        """
        An agent has run out of tokens and is asking Finance for more.
        Finance (CFO) approves/denies and notifies CEO (FYI).
        """
        p = envelope.get("payload", {})
        result = self.token_manager.handle_topup_request(
            agent_name=envelope.get("sender", ""),
            scenario_id=p.get("scenario_id", STANDARD_SCENARIO),
            requested_amount=p.get("requested_amount", 10),
            reason=p.get("reason", ""),
        )
        return result, "done"

    def _handle_token_balance_query(self, envelope: dict) -> tuple:
        """Any agent can query their current token balance."""
        agent = envelope.get("sender", "")
        scenario = envelope.get("payload", {}).get("scenario_id", STANDARD_SCENARIO)
        balance = self.token_manager.get_balance(agent, scenario)
        return {
            "agent": agent,
            "scenario_id": scenario,
            "balance": balance,
        }, "done"

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _send_reply(self, original: dict, payload: dict, status: str) -> None:
        reply = Message.create(
            sender=self.name,
            recipient=original.get("sender", "CEO"),
            task_type=f"{original.get('task_type', 'UNKNOWN')}_REPLY",
            payload=payload,
            status=status,
        )
        try:
            self.client.submit_message(reply)
        except Exception as exc:
            logger.warning("[Finance] Could not send reply: %s", exc)

    def _send_budget_alert(self, quarter: str, budget: dict) -> None:
        alert = Message.create(
            sender=self.name,
            recipient="CEO",
            task_type="BUDGET_ALERT",
            payload={
                "quarter":          quarter,
                "burn_pct":         budget["burn_pct"],
                "spent_usd":        budget["spent_usd"],
                "total_budget_usd": budget["total_budget_usd"],
                "alert":            "HIGH_BURN — immediate action required",
            },
        )
        self.client.submit_message(alert)
        logger.warning("[Finance] HIGH BURN ALERT sent to CEO.")

    def _escalate_to_ceo(self, original: dict, amount: float, category: str) -> None:
        msg = Message.create(
            sender=self.name,
            recipient="CEO",
            task_type="BUDGET_APPROVAL",
            payload={
                "amount_usd":   amount,
                "category":     category,
                "requested_by": original.get("sender", "unknown"),
                "note":         f"Allocation of ${amount:,.2f} exceeds $10,000 threshold.",
            },
        )
        self.client.submit_message(msg)
        logger.info("[Finance] Budget approval escalated to CEO: $%.2f", amount)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    import time

    logging.basicConfig(level=logging.INFO)
    logger.info("[Finance] Starting Finance Agent worker...")

    client = EnterpriseRouterClient.from_env(agent_name="Finance")
    agent = FinanceAgent(router_client=client)
    agent.startup()

    logger.info("[Finance] Polling for messages...")
    while True:
        try:
            handled = agent.run_once()
            if not handled:
                time.sleep(2)
        except KeyboardInterrupt:
            logger.info("[Finance] Shutting down.")
            break
        except Exception as exc:
            logger.exception("[Finance] Unexpected error: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
