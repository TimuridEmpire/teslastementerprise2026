import os
from typing import Optional, Dict, Any
from agent_transport import AGENT_MARKETING, drain_mailbox, submit
from message_schema import Message
from pm_tools import generate_features_llm, moscow_prioritize, create_project, add_request_to_project
from pm_storage import storage

# --- INTEGRATION: Import the enterprise logger utilities ---
from agent_logger import get_agent_logger, log_inter_agent_message

class PMAgent:
    def __init__(self, name="PM"):
        self.name = name
        self._active_project = None
        
        # --- INTEGRATION: Replace basic logging with the centralized agent logger ---
        self.logger = get_agent_logger(self.name)

    def run(self):
        msgs = drain_mailbox(self.name)
        for m in msgs:
            # --- INTEGRATION: Log the received envelope cleanly ---
            log_inter_agent_message(self.logger, m, direction="RECEIVING")
            
            task = m.get('task_type')
            if task == "DEFINE_Q2_ROADMAP":
                self.handle_define_roadmap(m)
            elif task == "REQUEST_FEATURES":
                self.handle_feature_request(m)
            else:
                self.logger.warning(f"PMAgent: Unhandled task {task}")

    def _ensure_active_project(self, project_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not project_id:
            return None
        if self._active_project and self._active_project.get("id") == project_id:
            return self._active_project
        project = storage.get_project(project_id)
        if project:
            self._active_project = project
        return project

    def _resolve_project_id(self, msg: Dict[str, Any]) -> Optional[str]:
        context_project_id = msg.get("context", {}).get("project_id")
        if context_project_id:
            return context_project_id
        if self._active_project:
            return self._active_project.get("id")
        return None

    def handle_define_roadmap(self, msg):
        self.logger.info(f"PMAgent received roadmap request: {msg['id']}")
        payload = msg['payload']
        goal = payload.get("business_goal", "")
        product = payload.get("product_name", "Product")

        project = create_project(name=product, goal=goal, payload=payload)
        self._ensure_active_project(project["id"])
        self.logger.info(f"PMAgent created project: {project['id']}")

        features = generate_features_llm(goal)
        self.logger.info(f"PMAgent features generated")

        prioritized = moscow_prioritize(features)
        self.logger.info(f"PMAgent backlog prioritized")

        storage.save_backlog(project["id"], prioritized)
        storage.add_project_event(
            source=self.name,
            event_type="roadmap_defined",
            project_id=project["id"],
            message_id=msg["id"],
            details={
                "product_name": product,
                "must_count": len(prioritized["must"]),
                "should_count": len(prioritized["should"]),
            },
        )

        add_request_to_project(project["id"], {
            "type": "roadmap",
            "message_id": msg["id"],
            "features": features
        })

        feature_list = prioritized["must"] + prioritized["should"]
        
        # --- INTEGRATION: Log outbound messages ---
        campaign_msg = Message.create(
            sender=self.name,
            recipient=AGENT_MARKETING,
            task_type="LAUNCH_CAMPAIGN",
            context={"project_id": project["id"]},
            payload={"product_name": product, "features": feature_list}
        )
        log_inter_agent_message(self.logger, campaign_msg, direction="SENDING")
        submit(campaign_msg)

        report_msg = Message.create(
            sender=self.name,
            recipient=AGENT_MARKETING,
            task_type="PM_REPORT",
            context={"project_id": project["id"]},
            payload={
                "project_name": product,
                "must_count": len(prioritized["must"]),
                "should_count": len(prioritized["should"]),
                "status": "roadmap_defined"
            }
        )
        log_inter_agent_message(self.logger, report_msg, direction="SENDING")
        submit(report_msg)

    def handle_feature_request(self, msg):
        self.logger.info(f"PMAgent received feature request: {msg['id']}")
        payload = msg['payload']
        goal = payload.get("goal", "")
        requester = msg['sender']

        features = generate_features_llm(goal)
        prioritized = moscow_prioritize(features)

        project_id = self._resolve_project_id(msg)
        self._ensure_active_project(project_id)
        if project_id:
            add_request_to_project(project_id, {
                "type": "feature_request",
                "requester": requester,
                "message_id": msg["id"],
                "features": features
            })
        storage.add_project_event(
            source=self.name,
            event_type="feature_response_prepared",
            project_id=project_id,
            message_id=msg["id"],
            details={"requester": requester, "goal": goal},
        )

        # --- INTEGRATION: Log outbound response ---
        response_msg = Message.create(
            sender=self.name,
            recipient=requester,
            task_type="FEATURE_RESPONSE",
            context={"project_id": project_id},
            payload={"features": prioritized}
        )
        log_inter_agent_message(self.logger, response_msg, direction="SENDING")
        submit(response_msg)