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
  - Notifies CEO (FYI) of all token decisions — approval authority is Finance/CFO
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Repo imports (use existing repo files, not external packages) ─────────────
from agents.base_agent import BaseAgent, CEO_APPROVAL_THRESHOLD_USD
from enterprise_router_client import EnterpriseRouterClient
from finance_schema import AgentMessage, TokenUsage          # repo's own schema
from finance_token_manager import (                          # our new file
    FinanceTokenManager,
    STANDARD_SCENARIO,
    BROADCAST_SCENARIO,
)
from finance_tools import (
    allocate_budget,
    generate_audit_report,
    generate_pl_report,
    get_budget_status,
    log_revenue,
    log_token_cost,
    monte_carlo_forecast,
)
from llm_provider import llm_json_object                     # updated provider
from message_schema import Message                           # router envelope

logger = logging.getLogger("finance_agent")

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
Keep responses under 900 tokens — you have a max_tokens budget of 1000.
"""


class FinanceAgent(BaseAgent):
    """
    Router-integrated Finance Agent.
    Inherits LLM calling, token budget, and CEO escalation from BaseAgent.
    Uses EnterpriseRouterClient for all message passing.
    """

    def __init__(self, router_client: EnterpriseRouterClient, bus=None, db=None):
        super().__init__(
            name="Finance",
            bus=bus,
            system_prompt=FINANCE_SYSTEM_PROMPT,
            db=db,
        )
        self.router_client = router_client
        self.token_manager = FinanceTokenManager(
            router_client=router_client,
            executive_name="CEO",
            cfo_name="Finance",
        )

    def startup(self) -> None:
        """Initialize token registry on first boot."""
        logger.info("[Finance] Initializing token registry...")
        self.token_manager.initialize_registry()
        logger.info("[Finance] Token registry ready.")

    async def escalate_to_ceo(self, task_type: str, reason: str, payload: dict) -> dict:
        """
        Notify CEO via the Enterprise Router instead of BaseAgent's local-bus
        implementation — FinanceAgent is router-integrated and has no
        in-memory MessageBus wired up (self.bus is None by default).
        """
        envelope = Message.create(
            sender=self.name,
            recipient="CEO",
            task_type=f"ESCALATION_{task_type}",
            context={"escalated": True, "escalated_at": datetime.now(timezone.utc).isoformat()},
            payload={"reason": reason, **payload},
        )
        try:
            self.router_client.submit_message(envelope)
        except Exception as exc:
            logger.warning("[Finance] Could not notify CEO of escalation: %s", exc)
        logger.info("[Finance] Escalated to CEO: %s", reason)
        approved = payload.get("amount_usd", 0) < 50_000
        return {
            "approved": approved,
            "ceo_note": "Approved via simulated CEO" if approved else "Rejected: over budget cap",
        }

    # ── Required by BaseAgent ABC ─────────────────────────────────────────────

    async def handle(self, message: AgentMessage):
        """Async handler required by BaseAgent. Dispatches by task_type."""
        task = message.task_type
        logger.info("[Finance] Handling: %s from %s", task, message.sender)

        handlers = {
            "GENERATE_PL_REPORT":   self._handle_pl_report,
            "BUDGET_APPROVAL":      self._handle_budget_approval,
            "CASH_FLOW_FORECAST":   self._handle_forecast,
            "REVENUE_LOG":          self._handle_revenue_log,
            "AUDIT_REPORT":         self._handle_audit,
            "MONTE_CARLO_SIM":      self._handle_monte_carlo,
            "TOKEN_TOPUP_REQUEST":  self._handle_token_topup_request,
            "TOKEN_BALANCE_QUERY":  self._handle_token_balance_query,
        }
        handler = handlers.get(task)
        if handler:
            return await handler(message)

        logger.warning("[Finance] Unknown task: %s", task)
        return message.reply({"error": f"Unknown task: {task}"}, status="error")

    # ── Main router poll loop ─────────────────────────────────────────────────

    def run_once(self) -> bool:
        """Fetch and process one message from the router. Returns True if handled."""
        envelope = self.router_client.fetch_next("Finance")
        if not envelope:
            return False

        task   = envelope.get("task_type", "")
        sender = envelope.get("sender", "")
        msg_id = envelope.get("id", "")
        logger.info("[Finance] Router message: %s from %s", task, sender)

        self.tokens.reset()  # fresh token budget per task (BaseAgent pattern)

        try:
            # Convert router envelope → AgentMessage for BaseAgent compatibility
            msg = AgentMessage.from_dict(envelope)

            import asyncio
            loop = asyncio.new_event_loop()
            reply_msg = loop.run_until_complete(self.handle(msg))
            loop.close()

            if reply_msg:
                self._submit_reply(reply_msg)

            self.router_client.ack(msg_id, "Finance")

        except Exception as exc:
            logger.exception("[Finance] Error handling %s: %s", task, exc)
            self.router_client.nack(msg_id, reason=str(exc), recipient="Finance")

        return True

    # ── Task handlers ─────────────────────────────────────────────────────────

    async def _handle_pl_report(self, msg: AgentMessage) -> AgentMessage:
        quarter = msg.payload.get("period", "Q2-2026")
        raw_pl  = generate_pl_report(quarter)
        budget  = get_budget_status(quarter)

        prompt = f"""Generate a concise CFO-style P&L summary for {quarter}.

Raw data:
{json.dumps(raw_pl, indent=2)}

Budget status:
{json.dumps(budget, indent=2)}

Return JSON with keys: summary (string), health (good/warning/critical),
key_risks (list of strings), recommendations (list of strings).
"""
        # Use BaseAgent's call_llm_structured (handles Ollama + token budget)
        result, usage = self.call_llm_structured(
            prompt,
            task_type="GENERATE_PL_REPORT",
            op="pl_report",
            preferred_role="analyst",
        )
        log_token_cost(
            "Finance", "GENERATE_PL_REPORT",
            usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.cost_usd,
        )

        if budget.get("burn_pct", 0) > 75:
            self._send_budget_alert(quarter, budget)

        reply = msg.reply({**result, "pl_data": raw_pl, "budget": budget}, status="done")
        reply.token_usage = usage.to_dict()
        return reply

    async def _handle_budget_approval(self, msg: AgentMessage) -> AgentMessage:
        amount   = msg.payload.get("amount_usd", 0)
        category = msg.payload.get("category", "general")
        quarter  = msg.payload.get("quarter", "Q2-2026")

        if amount > CEO_APPROVAL_THRESHOLD_USD:
            # Use BaseAgent's escalate_to_ceo
            ceo = await self.escalate_to_ceo(
                "BUDGET_APPROVAL",
                f"Requested allocation of ${amount:,.2f} exceeds $10,000 threshold",
                {"amount_usd": amount, "category": category},
            )
            if not ceo.get("approved"):
                return msg.reply({"approved": False, "reason": "CEO rejected"}, status="done")

        result = allocate_budget(quarter, amount, category)
        return msg.reply(result, status="done")

    async def _handle_forecast(self, msg: AgentMessage) -> AgentMessage:
        p  = msg.payload
        mc = monte_carlo_forecast(
            base_revenue_usd=p.get("base_monthly_revenue_usd", 50000),
            base_expense_usd=p.get("base_monthly_expense_usd", 45000),
            months=p.get("months", 6),
        )
        prompt = f"""Interpret this Monte Carlo cash flow simulation as a CFO would.

{json.dumps(mc, indent=2)}

Return JSON with: narrative (2-3 sentences), risk_level, top_actions (list of 3 short strings).
"""
        result, usage = self.call_llm_structured(
            prompt,
            task_type="CASH_FLOW_FORECAST",
            op="forecast",
            preferred_role="analyst",
        )
        log_token_cost(
            "Finance", "CASH_FLOW_FORECAST",
            usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.cost_usd,
        )
        reply = msg.reply({**mc, "llm_interpretation": result}, status="done")
        reply.token_usage = usage.to_dict()
        return reply

    async def _handle_revenue_log(self, msg: AgentMessage) -> AgentMessage:
        p      = msg.payload
        result = log_revenue(
            amount_usd=p.get("deal_value_usd", 0),
            deal_id=p.get("deal_id", ""),
            company=p.get("company", "Unknown"),
            quarter=p.get("quarter", "Q2-2026"),
        )
        logger.info(
            "[Finance] Revenue logged: $%.2f from %s (deal %s)",
            p.get("deal_value_usd", 0), p.get("company"), p.get("deal_id"),
        )
        return msg.reply(result, status="done")

    async def _handle_audit(self, msg: AgentMessage) -> AgentMessage:
        quarter = msg.payload.get("quarter", "Q2-2026")
        audit   = generate_audit_report(quarter)
        prompt  = f"""Review this audit report and flag any concerns.

{json.dumps(audit, indent=2)}

Return JSON with: findings (list), severity (low/medium/high), token_cost_summary (string).
"""
        result, usage = self.call_llm_structured(
            prompt,
            task_type="AUDIT_REPORT",
            op="audit",
            preferred_role="reporter",
        )
        log_token_cost(
            "Finance", "AUDIT_REPORT",
            usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.cost_usd,
        )
        reply = msg.reply({**audit, "llm_analysis": result}, status="done")
        reply.token_usage = usage.to_dict()
        return reply

    async def _handle_monte_carlo(self, msg: AgentMessage) -> AgentMessage:
        p  = msg.payload
        mc = monte_carlo_forecast(
            base_revenue_usd=p.get("base_revenue_usd", 50000),
            base_expense_usd=p.get("base_expense_usd", 45000),
            months=p.get("months", 6),
            simulations=p.get("simulations", 1000),
        )
        return msg.reply(mc, status="done")

    async def _handle_token_topup_request(self, msg: AgentMessage) -> AgentMessage:
        """
        An agent has run out of tokens and is asking Finance for more.
        Finance (CFO) approves/denies and notifies CEO (FYI only).
        """
        result = self.token_manager.handle_topup_request(
            agent_name=msg.sender,
            scenario_id=msg.payload.get("scenario_id", STANDARD_SCENARIO),
            requested_amount=msg.payload.get("requested_amount", 10),
            reason=msg.payload.get("reason", ""),
        )
        return msg.reply(result, status="done")

    async def _handle_token_balance_query(self, msg: AgentMessage) -> AgentMessage:
        scenario = msg.payload.get("scenario_id", STANDARD_SCENARIO)
        balance  = self.token_manager.get_balance(msg.sender, scenario)
        return msg.reply(
            {"agent": msg.sender, "scenario_id": scenario, "balance": balance},
            status="done",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _submit_reply(self, reply_msg: AgentMessage) -> None:
        """Convert AgentMessage → Message envelope and submit to router."""
        envelope = Message.create(
            sender="Finance",
            recipient=reply_msg.recipient,
            task_type=reply_msg.task_type,
            payload=reply_msg.payload,
            context=reply_msg.context,
            status=reply_msg.status,
            token_usage=reply_msg.token_usage or {},
        )
        try:
            self.router_client.submit_message(envelope)
        except Exception as exc:
            logger.warning("[Finance] Could not submit reply: %s", exc)

    def _send_budget_alert(self, quarter: str, budget: dict) -> None:
        alert = Message.create(
            sender="Finance",
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
        self.router_client.submit_message(alert)
        logger.warning("[Finance] HIGH BURN ALERT sent to CEO.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import time
    logging.basicConfig(level=logging.INFO)
    logger.info("[Finance] Starting Finance Agent worker...")

    client = EnterpriseRouterClient.from_env(agent_name="Finance")
    agent  = FinanceAgent(router_client=client)
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
