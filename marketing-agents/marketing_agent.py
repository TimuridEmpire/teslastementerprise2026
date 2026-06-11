import os
import re
from typing import Dict, Any, Optional, List

from agent_transport import (
    AGENT_CEO,
    AGENT_SALES,
    ack,
    drain_mailbox,
    local_fallback_enabled,
    nack,
    receive,
    submit,
)
from message_schema import Message
from marketing_tools import plan_campaign, save_campaign, generate_email, generate_image_prompt
from pm_storage import storage
from artifact_writer import render_campaign_brief_md, write_artifact, publish_artifact
from agent_logger import get_agent_logger, log_inter_agent_message

BUDGET_APPROVAL_THRESHOLD = 10000

# Delimiters a planner might use between channels: "+", ",", "&", "/", or " and ".
_CHANNEL_SPLIT_RE = re.compile(r"\s*(?:\+|,|&|/|\band\b)\s*", flags=re.IGNORECASE)


def _split_channels(channel: str) -> List[str]:
    """
    Normalise a free-form channel string into a clean list for channel_mix.

    Handles "Email + Social Media", "Email, Social, Search",
    "Email & SMS", "Email/Social", "Email and Social" -> list of channels.
    Empty / missing input yields an empty list rather than [''].
    """
    if not channel:
        return []
    return [c.strip() for c in _CHANNEL_SPLIT_RE.split(channel) if c.strip()]


class MarketingAgent:
    def __init__(self, name: str = "Marketing") -> None:
        self.name = name
        self.logger = get_agent_logger(self.name)

    # ------------------------------------------------------------------
    # Main poll entry-point
    #
    # Called once per poll cycle by run_single_agent.py's run_drain_agent().
    # Router mode: IDLE -> lease ONE message -> BUSY -> ack/nack -> IDLE.
    # run_single_agent re-invokes run() on the next poll interval.
    #
    # Offline/demo mode (ENTERPRISE_ROUTER_OFFLINE_DEMO=1): the local
    # MessageBus has no lease concept, so we drain all queued messages at
    # once. That path is test/demo only and does not ack/nack.
    # ------------------------------------------------------------------
    def run(self) -> None:
        if local_fallback_enabled():
            msgs = drain_mailbox(self.name)
            for m in msgs:
                self._process(m, use_router=False)
        else:
            m = receive(self.name)
            if m is not None:
                self._process(m, use_router=True)

    def _process(self, m: Dict[str, Any], *, use_router: bool) -> None:
        """Dispatch a single message and ack/nack when done (router mode only)."""
        log_inter_agent_message(self.logger, m, direction="RECEIVING")
        try:
            task_type = m.get("task_type")
            if task_type == "LAUNCH_CAMPAIGN":
                self.handle_launch_campaign(m)
            elif task_type == "PM_REPORT":
                self.handle_pm_report(m)
            else:
                self.logger.warning(f"MarketingAgent: unhandled task_type '{task_type}'")

            if use_router:
                ack(str(m.get("id", "")), self.name)

        except Exception as exc:
            self.logger.error(
                f"MarketingAgent: error processing {m.get('id')}: {exc}", exc_info=True
            )
            if use_router:
                nack(str(m.get("id", "")), self.name, reason=str(exc))
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_context(self, msg: Dict[str, Any], project_id: Optional[str]) -> Dict[str, Any]:
        run_id = msg.get("context", {}).get("run_id", "")
        ctx: Dict[str, Any] = {"source_message_id": msg.get("id", "")}
        if project_id:
            ctx["project_id"] = project_id
        if run_id:
            ctx["run_id"] = run_id
        return ctx

    def _generate_creative_assets(
        self,
        msg: Dict[str, Any],
        product: str,
        features: List[Any],
        campaign: Dict[str, Any],
        project_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Generate the email + image prompt, render the campaign brief, write it
        as an artifact and announce it to CEO.

        Runs for EVERY launch campaign regardless of the budget branch, so an
        ad-campaign email is always produced -- even when the campaign is held
        for CEO budget approval. Returns the generated email dict.
        """
        email = generate_email(
            product=product,
            tagline=campaign.get("tagline", ""),
            features=features,
        )
        self.logger.info(f"MarketingAgent: email subject -- {email.get('subject')}")

        image_prompt = generate_image_prompt(
            product=product,
            tagline=campaign.get("tagline", ""),
            features=features,
        )
        self.logger.info(
            f"MarketingAgent: image prompt -- {image_prompt.get('prompt', '')[:80]}"
        )

        brief_md = render_campaign_brief_md(product, campaign, email, image_prompt)
        brief_artifact = write_artifact(
            agent=self.name,
            name="campaign_brief",
            content=brief_md,
            project_id=project_id,
        )
        self.logger.info(
            f"MarketingAgent: campaign brief written to {brief_artifact['path']}"
        )
        # Non-fatal: a failure logs a warning and never raises.
        publish_artifact(brief_artifact, source_msg=msg)
        return email

    # ------------------------------------------------------------------
    # Task handlers
    # ------------------------------------------------------------------

    def handle_pm_report(self, msg: Dict[str, Any]) -> None:
        self.logger.info(f"MarketingAgent: handling PM_REPORT {msg.get('id')}")
        project_id = msg.get("context", {}).get("project_id")
        storage.add_project_event(
            source=self.name,
            event_type="pm_report_received",
            project_id=project_id,
            message_id=msg.get("id"),
            details=msg.get("payload", {}),
        )

    def handle_launch_campaign(self, msg: Dict[str, Any]) -> None:
        self.logger.info(f"MarketingAgent: handling LAUNCH_CAMPAIGN {msg.get('id')}")
        payload = msg.get("payload", {})
        product = payload.get("product_name", "Product")
        features = payload.get("features", [])
        project_id = msg.get("context", {}).get("project_id")

        campaign = plan_campaign(product, features)
        campaign["project_id"] = project_id
        self.logger.info(f"MarketingAgent: campaign planned -- budget ${campaign.get('budget', 0)}")

        budget = campaign.get("budget", 0)
        base_ctx = self._base_context(msg, project_id)

        if budget > BUDGET_APPROVAL_THRESHOLD:
            # Budget requires CEO approval before the campaign can launch.
            # We do NOT save the campaign or notify Sales yet, but we still
            # generate the creative assets (email/visual/brief) below so the
            # CEO can review them alongside the approval request.
            approval_msg = Message.create(
                sender=self.name,
                recipient=AGENT_CEO,
                task_type="BUDGET_APPROVAL",
                context=base_ctx,
                payload={
                    "product_name": product,
                    "initiative": f"Marketing campaign for {product}",
                    "budget": budget,
                    "expected_leads": campaign.get("expected_leads", 0),
                    "justification": (
                        f"Campaign budget of ${budget} exceeds the "
                        f"${BUDGET_APPROVAL_THRESHOLD} threshold and requires CEO approval."
                    ),
                },
            )
            log_inter_agent_message(self.logger, approval_msg, direction="SENDING")
            submit(approval_msg)

            storage.add_project_event(
                source=self.name,
                event_type="budget_approval_requested",
                project_id=project_id,
                message_id=msg.get("id"),
                details={"product_name": product, "budget": budget},
            )
            self.logger.info(
                f"MarketingAgent: budget ${budget} exceeds threshold -- "
                "sent BUDGET_APPROVAL to CEO"
            )

        else:
            # Budget is within limits -- save campaign and notify Sales.
            save_campaign(campaign)
            storage.add_project_event(
                source=self.name,
                event_type="campaign_saved",
                project_id=project_id,
                message_id=msg.get("id"),
                details={"product_name": product, "budget": budget},
            )
            self.logger.info("MarketingAgent: campaign saved")

            launch_msg = Message.create(
                sender=self.name,
                recipient=AGENT_SALES,
                task_type="CAMPAIGN_LAUNCHED",
                context=base_ctx,
                payload={
                    "product_name": product,
                    "channel_mix": _split_channels(campaign.get("channel", "")),
                    "budget": budget,
                    "expected_leads": campaign.get("expected_leads", 0),
                    "lead_list_forwarded_to_sales": True,
                },
            )
            log_inter_agent_message(self.logger, launch_msg, direction="SENDING")
            submit(launch_msg)
            self.logger.info("MarketingAgent: CAMPAIGN_LAUNCHED sent to Sales")

        # Creative assets (incl. the ad-campaign email) are generated for both
        # branches -- approval-pending and launched alike.
        self._generate_creative_assets(msg, product, features, campaign, project_id)
