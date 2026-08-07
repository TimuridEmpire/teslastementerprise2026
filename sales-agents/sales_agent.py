"""
sales-agents/sales_agent.py - Sales Agent router worker.

Responsibilities:
  - Prospect and qualify leads
  - Generate personalized pitches
  - Close deals and log revenue to Finance
  - Publish pipeline/deal artifacts for the website live output panels
"""

from __future__ import annotations

import json
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (ROOT, os.path.dirname(__file__), os.path.join(ROOT, "finance-agents")):
    if path and path not in sys.path:
        sys.path.insert(0, path)

from agents.base_agent import BaseAgent
from enterprise_router.agent_artifacts import write_agent_artifact
from enterprise_router_client import EnterpriseRouterClient
from finance_schema import AgentMessage
from finance_tools import log_token_cost
from message_schema import Message
from sales_tools import (
    close_deal,
    generate_pitch,
    get_pipeline_report,
    identify_upsell_opportunities,
    qualify_lead,
)

logger = logging.getLogger("sales_agent")

SALES_SYSTEM_PROMPT = """You are the Sales Agent for an AI-simulated enterprise.

Your role:
- Qualify leads using BANT criteria
- Generate personalized pitches tailored to buyer segment
- Handle objections and close deals
- Identify upsell opportunities
- Report pipeline metrics and revenue to CEO and Finance

Decision rules:
1. Only pursue leads with qualification score >= 50.
2. Escalate deals > $50,000 to CEO for final approval.
3. After every closed_won deal, immediately send a REVENUE_LOG message to Finance.
4. Prioritize enterprise leads when the pipeline is full.

Always respond in JSON. Keep responses under 900 tokens.
"""


class SalesAgent(BaseAgent):
    def __init__(self, router_client: EnterpriseRouterClient | None = None, bus=None, db=None):
        super().__init__(name="Sales", bus=bus, system_prompt=SALES_SYSTEM_PROMPT, db=db)
        self.router_client = router_client or EnterpriseRouterClient.from_env(agent_name="Sales")

    async def handle(self, message: AgentMessage):
        task = message.task_type
        logger.info("[Sales] Handling: %s from %s", task, message.sender)

        handlers = {
            "CAMPAIGN_LAUNCHED": self._handle_campaign_launched,
            "QUALIFY_LEAD": self._handle_qualify,
            "GENERATE_PITCH": self._handle_pitch,
            "CLOSE_DEAL": self._handle_close,
            "UPSELL": self._handle_upsell,
            "PIPELINE_REPORT": self._handle_pipeline,
            "DEMO_REQUEST": self._handle_demo,
        }
        handler = handlers.get(task)
        if handler:
            return await handler(message)

        logger.warning("[Sales] Unknown task: %s", task)
        return message.reply({"error": f"Unknown task: {task}"}, status="error")

    def run_once(self) -> bool:
        """Fetch and process one message from the router. Returns True if handled."""
        envelope = self.router_client.fetch_next("Sales")
        if not envelope:
            return False

        task = envelope.get("task_type", "")
        sender = envelope.get("sender", "")
        msg_id = str(envelope.get("id", ""))
        logger.info("[Sales] Router message: %s from %s", task, sender)
        self.tokens.reset()

        try:
            msg = AgentMessage.from_dict(envelope)
            import asyncio

            loop = asyncio.new_event_loop()
            reply_msg = loop.run_until_complete(self.handle(msg))
            loop.close()

            if reply_msg:
                self._submit_reply(reply_msg)
            self.router_client.ack(msg_id, "Sales")
        except Exception as exc:
            logger.exception("[Sales] Error handling %s: %s", task, exc)
            self.router_client.nack(msg_id, reason=str(exc), recipient="Sales")
        return True

    def _write_artifact(self, msg: AgentMessage, title: str, artifact_type: str, result: dict) -> None:
        body = (
            f"## Source task\n\n{msg.task_type} from {msg.sender}\n\n"
            "## Result\n\n```json\n"
            + json.dumps(result, indent=2, default=str)
            + "\n```"
        )
        write_agent_artifact(
            "Sales",
            title=title,
            body=body,
            artifact_type=artifact_type,
            metadata={"source": "sales_agent", "sender": msg.sender, "task_type": msg.task_type},
            source_message_id=msg.id,
            source_task_type=msg.task_type,
        )

    def _submit_reply(self, reply_msg: AgentMessage) -> None:
        envelope = Message.create(
            sender="Sales",
            recipient=reply_msg.recipient,
            task_type=reply_msg.task_type,
            payload=reply_msg.payload,
            context=reply_msg.context,
            status=reply_msg.status,
        )
        try:
            self.router_client.submit_message(envelope)
        except Exception as exc:
            logger.warning("[Sales] Could not submit reply: %s", exc)

    def _submit_revenue_log(self, msg: AgentMessage, result: dict, final_value: float) -> None:
        revenue_msg = Message.create(
            sender="Sales",
            recipient="Finance",
            task_type="REVENUE_LOG",
            payload={
                "deal_id": result["deal_id"],
                "company": result["company"],
                "deal_value_usd": final_value,
                "quarter": msg.context.get("quarter", "Q2-2026"),
            },
            context={**msg.context, "auto_logged": True, "source_message_id": msg.id},
        )
        self.router_client.submit_message(revenue_msg)
        logger.info("[Sales] REVENUE_LOG -> Finance: $%.2f - %s", final_value, result["company"])

    async def _handle_campaign_launched(self, msg: AgentMessage):
        report = get_pipeline_report()
        payload = {
            "campaign": msg.payload,
            "pipeline_snapshot": report,
            "next_action": "Qualify campaign leads and prioritize enterprise prospects.",
        }
        self._write_artifact(msg, "Campaign launch received", "sales_campaign_intake", payload)
        return msg.reply(payload, status="done")

    async def _handle_qualify(self, msg: AgentMessage):
        lead_id = msg.payload.get("lead_id", "")
        if not lead_id:
            payload = {"error": "lead_id required"}
            self._write_artifact(msg, "Lead qualification failed", "sales_qualification", payload)
            return msg.reply(payload, status="error")

        qual = qualify_lead(lead_id)
        prompt = f"""You are a senior sales rep reviewing a lead qualification result.

Lead data:
{json.dumps(qual, indent=2)}

Return JSON with strategy, next_step, and priority.
"""
        result, usage = self.call_llm_structured(
            prompt, task_type="QUALIFY_LEAD", op="qualify", preferred_role="analyst"
        )
        log_token_cost("Sales", "QUALIFY_LEAD", usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.cost_usd)
        payload = {**qual, "llm_strategy": result}
        self._write_artifact(msg, f"Lead qualification for {lead_id}", "sales_qualification", payload)
        reply = msg.reply(payload, status="done")
        reply.token_usage = usage.to_dict()
        return reply

    async def _handle_pitch(self, msg: AgentMessage):
        lead_id = msg.payload.get("lead_id", "")
        objection = msg.payload.get("objection")
        base_pitch = generate_pitch(lead_id)
        if "error" in base_pitch:
            self._write_artifact(msg, "Pitch generation failed", "sales_pitch", base_pitch)
            return msg.reply(base_pitch, status="error")

        objection_context = f"\n\nThe prospect raised this objection: '{objection}'. Address it directly." if objection else ""
        prompt = f"""Enhance this pitch to be more compelling and natural.{objection_context}

Base pitch:
{base_pitch['pitch']}

Segment: {base_pitch['segment']}

Return JSON with enhanced_pitch, subject_line, objection_response, and confidence_score.
"""
        result, usage = self.call_llm_structured(
            prompt, task_type="GENERATE_PITCH", op="pitch", preferred_role="executor"
        )
        log_token_cost("Sales", "GENERATE_PITCH", usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.cost_usd)
        payload = {**base_pitch, "llm_enhanced": result}
        self._write_artifact(msg, f"Sales pitch for {lead_id}", "sales_pitch", payload)
        reply = msg.reply(payload, status="done")
        reply.token_usage = usage.to_dict()
        return reply

    async def _handle_close(self, msg: AgentMessage):
        lead_id = msg.payload.get("lead_id", "")
        final_value = msg.payload.get("final_value_usd", 0)
        won = msg.payload.get("won", True)

        if final_value > 50_000:
            approval = Message.create(
                sender="Sales",
                recipient="CEO",
                task_type="CEO_REASONING_LOOP",
                payload={
                    "message": f"Sales requests approval to close {lead_id} for ${final_value:,.2f}.",
                    "lead_id": lead_id,
                    "amount_usd": final_value,
                },
                context={**msg.context, "source_message_id": msg.id, "approval_required": True},
            )
            self.router_client.submit_message(approval)
            payload = {"status": "blocked", "reason": "CEO approval requested", "lead_id": lead_id}
            self._write_artifact(msg, f"Deal approval requested for {lead_id}", "sales_deal", payload)
            return msg.reply(payload, status="done")

        result = close_deal(lead_id, final_value, won)
        if won and "deal_id" in result:
            self._submit_revenue_log(msg, result, final_value)
        self._write_artifact(msg, f"Deal result for {lead_id}", "sales_deal", result)
        return msg.reply(result, status="done")

    async def _handle_upsell(self, msg: AgentMessage):
        opportunities = identify_upsell_opportunities()
        prompt = f"""Review these upsell opportunities.

{json.dumps(opportunities, indent=2)}

Return JSON with top_3, total_upsell_value_usd, and outreach_strategy.
"""
        result, usage = self.call_llm_structured(
            prompt, task_type="UPSELL", op="upsell", preferred_role="analyst"
        )
        log_token_cost("Sales", "UPSELL", usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.cost_usd)
        payload = {"opportunities": opportunities, "llm_analysis": result}
        self._write_artifact(msg, "Upsell opportunities", "sales_upsell", payload)
        reply = msg.reply(payload, status="done")
        reply.token_usage = usage.to_dict()
        return reply

    async def _handle_pipeline(self, msg: AgentMessage):
        report = get_pipeline_report()
        prompt = f"""Summarize this sales pipeline report for the CEO.

{json.dumps(report, indent=2)}

Return JSON with executive_summary, pipeline_health, and top_priority.
"""
        result, usage = self.call_llm_structured(
            prompt, task_type="PIPELINE_REPORT", op="pipeline", preferred_role="reporter"
        )
        log_token_cost("Sales", "PIPELINE_REPORT", usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.cost_usd)
        payload = {**report, "llm_summary": result}
        self._write_artifact(msg, "Sales pipeline report", "sales_pipeline", payload)
        reply = msg.reply(payload, status="done")
        reply.token_usage = usage.to_dict()
        return reply

    async def _handle_demo(self, msg: AgentMessage):
        lead_id = msg.payload.get("lead_id", "")
        qual = qualify_lead(lead_id)
        prompt = f"""Prepare a 30-minute demo agenda for this prospect.

Lead info:
{json.dumps(qual, indent=2)}

Return JSON with agenda, key_value_props, and success_criteria.
"""
        result, usage = self.call_llm_structured(
            prompt, task_type="DEMO_REQUEST", op="demo", preferred_role="executor"
        )
        log_token_cost("Sales", "DEMO_REQUEST", usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.cost_usd)
        payload = {"lead": qual, "demo_plan": result}
        self._write_artifact(msg, f"Demo plan for {lead_id}", "sales_demo", payload)
        reply = msg.reply(payload, status="done")
        reply.token_usage = usage.to_dict()
        return reply


def main() -> None:
    import time

    logging.basicConfig(level=logging.INFO)
    logger.info("[Sales] Starting Sales Agent worker...")
    agent = SalesAgent(router_client=EnterpriseRouterClient.from_env(agent_name="Sales"))
    logger.info("[Sales] Polling for messages...")
    while True:
        try:
            handled = agent.run_once()
            if not handled:
                time.sleep(2)
        except KeyboardInterrupt:
            logger.info("[Sales] Shutting down.")
            break
        except Exception as exc:
            logger.exception("[Sales] Unexpected error: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
