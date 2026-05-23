import os
from agent_transport import AGENT_CEO, AGENT_SALES, drain_mailbox, submit
from message_schema import Message
from marketing_tools import plan_campaign, save_campaign, generate_email, generate_image_prompt
from pm_storage import storage

# --- INTEGRATION: Import the enterprise logger utilities ---
from agent_logger import get_agent_logger, log_inter_agent_message

budget_approval_threshold = 10000

class MarketingAgent:
    def __init__(self, name="Marketing"):
        self.name = name
        
        # --- INTEGRATION: Replace basic logging with the centralized agent logger ---
        self.logger = get_agent_logger(self.name)

    def run(self):
        msgs = drain_mailbox(self.name)
        for m in msgs:
            # --- INTEGRATION: Log the received envelope cleanly ---
            log_inter_agent_message(self.logger, m, direction="RECEIVING")
            
            task_type = m.get('task_type')
            if task_type == "LAUNCH_CAMPAIGN":
                self.handle_launch_campaign(m)
            elif task_type == "PM_REPORT":
                self.handle_pm_report(m)
            else:
                self.logger.warning(f"MarketingAgent: Unhandled {task_type}")

    def handle_pm_report(self, msg):
        self.logger.info(f"MarketingAgent received PM report: {msg.get('id')}")
        project_id = msg.get("context", {}).get("project_id")
        storage.add_project_event(
            source=self.name,
            event_type="pm_report_received",
            project_id=project_id,
            message_id=msg.get("id"),
            details=msg.get("payload", {}),
        )

    def handle_launch_campaign(self, msg):
        self.logger.info(f"MarketingAgent received campaign request: {msg.get('id')}")
        payload = msg.get('payload', {})
        product = payload.get("product_name", "Product")
        features = payload.get("features", [])
        project_id = msg.get("context", {}).get("project_id")

        campaign = plan_campaign(product, features)
        campaign["project_id"] = project_id
        self.logger.info(f"MarketingAgent plan: {campaign}")

        budget = campaign.get("budget", 0)

        if budget > budget_approval_threshold:
            # --- INTEGRATION: Create, log, and send the budget approval message ---
            approval_msg = Message.create(
                sender=self.name,
                recipient=AGENT_CEO,
                task_type="BUDGET_APPROVAL",
                context={"project_id": project_id},
                payload={
                    "product_name": product,
                    "initiative": f"Marketing campaign for {product}",
                    "budget": budget,
                    "expected_leads": campaign.get("expected_leads", 0),
                    "justification": f"Campaign budget of ${budget} exceeds the ${budget_approval_threshold} threshold and requires CEO approval.",
                }
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
            self.logger.info(f"MarketingAgent: budget ${budget} exceeds threshold, sent BUDGET_APPROVAL to CEO")

        else:
            save_campaign(campaign)
            storage.add_project_event(
                source=self.name,
                event_type="campaign_saved",
                project_id=project_id,
                message_id=msg.get("id"),
                details={"product_name": product, "budget": budget},
            )
            self.logger.info("MarketingAgent: campaign saved")

            # --- INTEGRATION: Create, log, and send the campaign launch message ---
            launch_msg = Message.create(
                sender=self.name,
                recipient=AGENT_SALES,
                task_type="CAMPAIGN_LAUNCHED",
                context={"project_id": project_id},
                payload={
                    "product_name": product,
                    "channel_mix": campaign.get("channel", "").split(" + "),
                    "budget": budget,
                    "expected_leads": campaign.get("expected_leads", 0),
                    "lead_list_forwarded_to_sales": True,
                }
            )
            log_inter_agent_message(self.logger, launch_msg, direction="SENDING")
            submit(launch_msg)
            
            self.logger.info("MarketingAgent: CAMPAIGN_LAUNCHED sent to Sales")
            
            email = generate_email(
                product=product,
                tagline=campaign.get("tagline", ""),
                features=features,
            )
            self.logger.info(f"MarketingAgent email subject: {email.get('subject')}")

            image_prompt = generate_image_prompt(
                product=product,
                tagline=campaign.get("tagline", ""),
                features=features,
            )
            self.logger.info(f"MarketingAgent image prompt: {image_prompt.get('prompt', '')[:80]}")