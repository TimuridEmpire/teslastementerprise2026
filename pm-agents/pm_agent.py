gemiimport os
from typing import Optional, Dict, Any
from agent_transport import AGENT_MARKETING, ack, drain_mailbox, local_fallback_enabled, nack, receive, submit
from message_schema import Message
from pm_tools import generate_features_llm, moscow_prioritize, create_project, add_request_to_project, decide_routes
from pm_storage import storage
from artifact_writer import render_roadmap_md, write_artifact

# --- INTEGRATION: Import the enterprise logger utilities ---
from agent_logger import get_agent_logger, log_inter_agent_message

class PMAgent:
    def __init__(self, name="PM"):
        self.name = name
        self._active_project = None
        
        # --- INTEGRATION: Replace basic logging with the centralized agent logger ---
        self.logger = get_agent_logger(self.name)

    def run(self):
        if local_fallback_enabled():
            msgs = drain_mailbox(self.name)
        else:
            msgs = []
            while True:
                msg = receive(self.name)
                if msg is None:
                    break
                msgs.append(msg)

        for m in msgs:
            # --- INTEGRATION: Log the received envelope cleanly ---
            log_inter_agent_message(self.logger, m, direction="RECEIVING")

            try:
                task = m.get('task_type')
                if task == "DEFINE_Q2_ROADMAP":
                    self.handle_define_roadmap(m)
                elif task == "REQUEST_FEATURES":
                    self.handle_feature_request(m)
                else:
                    self.logger.warning(f"PMAgent: Unhandled task {task}")
                if not local_fallback_enabled():
                    ack(str(m.get("id", "")), self.name)
            except Exception as exc:
                if not local_fallback_enabled():
                    nack(str(m.get("id", "")), self.name, reason=str(exc))
                raise

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

        # --- Item 2: roadmap artifact (markdown) ---
        roadmap_md = render_roadmap_md(product, goal, prioritized)
        roadmap_artifact = write_artifact(
            agent=self.name,
            name="roadmap",
            content=roadmap_md,
            project_id=project["id"],
        )
        self.logger.info(f"PMAgent wrote roadmap artifact: {roadmap_artifact['path']}")

        # --- Item 3: decide recipients, then send each routed message ---
        routes = decide_routes(
            product=product,
            goal=goal,
            prioritized=prioritized,
            project_id=project["id"],
            artifact_path=roadmap_artifact["path"],
        )
        for route in routes:
            out_msg = Message.create(
                sender=self.name,
                recipient=route["recipient"],
                task_type=route["task_type"],
                context=route["context"],
                payload=route["payload"],
            )
            log_inter_agent_message(self.logger, out_msg, direction="SENDING")
            submit(out_msg)
        self.logger.info(f"PMAgent sent {len(routes)} routed messages")

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
