import json
import os
from typing import Optional, Dict, Any

from agent_transport import (
    AGENT_CEO,
    AGENT_ENGINEERING,
    AGENT_HR,
    AGENT_MARKETING,
    ack,
    drain_mailbox,
    local_fallback_enabled,
    nack,
    receive,
    submit,
)
from message_schema import Message
from pm_tools import (
    generate_features_llm,
    moscow_prioritize,
    create_project,
    add_request_to_project,
    decide_routes,
    derive_target_release,
)
from pm_storage import storage
from artifact_writer import render_roadmap_md, write_artifact, publish_artifact
from agent_backlog import AgentBacklog
from agent_logger import get_agent_logger, log_inter_agent_message

try:
    from enterprise_router.agent_artifacts import write_agent_artifact
except ImportError:  # pragma: no cover - artifact API is optional in isolated PM tests
    write_agent_artifact = None

try:  # pragma: no cover - RAG retrieval is additive/optional
    from enterprise_router.vector_storage import format_rag_context_block, retrieve_rag_context
except ImportError:  # pragma: no cover - RAG retrieval is optional in isolated PM tests
    retrieve_rag_context = None
    format_rag_context_block = None


class PMAgent:
    def __init__(self, name: str = "PM") -> None:
        self.name = name
        self._active_project: Optional[Dict[str, Any]] = None
        self.logger = get_agent_logger(self.name)
        self.backlog = AgentBacklog()

    # ------------------------------------------------------------------
    # Main poll entry-point
    #
    # Called once per poll cycle by run_single_agent.py's run_drain_agent().
    # The guide requires IDLE -> fetch ONE message -> BUSY -> ack/nack -> IDLE.
    #
    # In offline/demo mode (ENTERPRISE_ROUTER_OFFLINE_DEMO=1) the local
    # MessageBus has no lease concept, so we drain all queued messages at once
    # just as before -- that path is test/demo only and does not go through
    # the real router.
    # ------------------------------------------------------------------
    def run(self) -> None:
        if local_fallback_enabled():
            # Offline demo: drain everything from the in-process bus.
            msgs = drain_mailbox(self.name)
            for m in msgs:
                self._process(m, use_router=False)
        else:
            # Router mode: fetch exactly ONE leased message, process it,
            # then ack/nack before returning.  run_single_agent will call
            # run() again on the next poll interval.
            m = receive(self.name)
            if m is not None:
                self._process(m, use_router=True)

    def _process(self, m: Dict[str, Any], *, use_router: bool) -> None:
        """Dispatch a single message and ack/nack when done."""
        log_inter_agent_message(self.logger, m, direction="RECEIVING")
        self.backlog.record_interaction(m)
        try:
            task = m.get("task_type")
            if task == "DEFINE_Q2_ROADMAP":
                self.handle_define_roadmap(m)
            elif task == "REQUEST_FEATURES":
                self.handle_feature_request(m)
            elif task == "CEO_STRATEGY_DIRECTIVE":
                self.handle_ceo_strategy_directive(m)
            elif task == "FEATURE_RESPONSE":
                self.handle_engineering_feature_response(m)
            elif task == "MANAGER_INTERVENTION":
                self.handle_manager_intervention(m)
            else:
                self.logger.warning(f"PMAgent: unhandled task_type '{task}'")

            if use_router:
                ack(str(m.get("id", "")), self.name)

        except Exception as exc:
            self.logger.error(f"PMAgent: error processing {m.get('id')}: {exc}", exc_info=True)
            if use_router:
                nack(str(m.get("id", "")), self.name, reason=str(exc))
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

    def _base_context(self, msg: Dict[str, Any], project_id: Optional[str]) -> Dict[str, Any]:
        """
        Build the correlation context that every outbound message must carry.

        The guide requires:
          - project_id   : groups messages belonging to the same project
          - source_message_id : the id of the inbound message that triggered
                                this outbound one (enables end-to-end tracing)
          - run_id       : propagated from the inbound message when present,
                           so the entire workflow can be correlated in the UI
        """
        run_id = msg.get("context", {}).get("run_id", "")
        ctx: Dict[str, Any] = {
            "source_message_id": msg.get("id", ""),
        }
        if project_id:
            ctx["project_id"] = project_id
        if run_id:
            ctx["run_id"] = run_id
        return ctx

    # ------------------------------------------------------------------
    # Task handlers
    # ------------------------------------------------------------------

    def _related_roadmaps_context(self, goal: str) -> str:
        """
        Semantic cross-reference against previously indexed PM roadmap
        artifacts sharing conceptual/contextual meaning with ``goal`` (not
        keyword matching against ``pm_storage.json``). Best-effort: returns
        ``""`` when RAG retrieval is unavailable, disabled, or the local
        embedding service is unreachable — roadmap creation must keep
        working with or without it.
        """
        if retrieve_rag_context is None or format_rag_context_block is None or not goal:
            return ""
        try:
            hits = retrieve_rag_context(goal, source_type="roadmap", top_k=3)
        except Exception as exc:
            self.logger.warning(
                "Roadmap RAG cross-reference failed, continuing without it: %s", exc
            )
            return ""
        return format_rag_context_block(hits, header="Related prior roadmaps") if hits else ""

    def handle_define_roadmap(self, msg: Dict[str, Any]) -> None:
        self.logger.info(f"PMAgent: handling DEFINE_Q2_ROADMAP {msg['id']}")
        payload = msg["payload"]
        goal = payload.get("business_goal", "")
        product = payload.get("product_name", "Product")

        project = create_project(name=product, goal=goal, payload=payload)
        self._ensure_active_project(project["id"])
        self.logger.info(f"PMAgent: project created {project['id']}")

        features = generate_features_llm(goal)
        self.logger.info("PMAgent: features generated")

        prioritized = moscow_prioritize(features)
        self.logger.info("PMAgent: backlog prioritized")

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
            "features": features,
        })

        # Write the roadmap artifact and announce it to CEO.
        roadmap_md = render_roadmap_md(product, goal, prioritized)
        related_roadmaps_block = self._related_roadmaps_context(goal)
        if related_roadmaps_block:
            roadmap_md = f"{roadmap_md}\n\n{related_roadmaps_block}\n"
        roadmap_artifact = write_artifact(
            agent=self.name,
            name="roadmap",
            content=roadmap_md,
            project_id=project["id"],
        )
        self.logger.info(f"PMAgent: roadmap artifact written to {roadmap_artifact['path']}")
        if write_agent_artifact is not None:
            write_agent_artifact(
                self.name,
                title=f"{product} Roadmap",
                body=roadmap_md,
                artifact_type="roadmap",
                metadata={
                    "project_id": project["id"],
                    "product_name": product,
                    "source": "DEFINE_Q2_ROADMAP",
                },
                source_message_id=str(msg.get("id", "")),
                source_task_type="DEFINE_Q2_ROADMAP",
            )
        # publish_artifact() sends ARTIFACT_PUBLISHED to CEO via the router.
        # It is non-fatal: a failure logs a warning and never raises.
        publish_artifact(roadmap_artifact, source_msg=msg)

        # Decide downstream recipients and send one message per route.
        # decide_routes() returns dicts with recipient/task_type/context/payload;
        # we merge our correlation context in here so every outbound message
        # carries source_message_id and run_id.
        base_ctx = self._base_context(msg, project["id"])
        routes = decide_routes(
            product=product,
            goal=goal,
            prioritized=prioritized,
            project_id=project["id"],
            artifact_path=roadmap_artifact["path"],
            target_release=derive_target_release(msg.get("context", {})),
        )
        for route in routes:
            # Merge base correlation context with any route-specific context.
            merged_ctx = {**base_ctx, **route["context"]}
            out_msg = Message.create(
                sender=self.name,
                recipient=route["recipient"],
                task_type=route["task_type"],
                context=merged_ctx,
                payload=route["payload"],
            )
            log_inter_agent_message(self.logger, out_msg, direction="SENDING")
            self.backlog.record_interaction(out_msg)
            submit(out_msg)

        self.logger.info(f"PMAgent: sent {len(routes)} downstream messages")

    def handle_feature_request(self, msg: Dict[str, Any]) -> None:
        self.logger.info(f"PMAgent: handling REQUEST_FEATURES {msg['id']}")
        payload = msg["payload"]
        goal = payload.get("goal", "")
        requester = msg["sender"]

        features = generate_features_llm(goal)
        prioritized = moscow_prioritize(features)

        project_id = self._resolve_project_id(msg)
        self._ensure_active_project(project_id)
        if project_id:
            add_request_to_project(project_id, {
                "type": "feature_request",
                "requester": requester,
                "message_id": msg["id"],
                "features": features,
            })
        storage.add_project_event(
            source=self.name,
            event_type="feature_response_prepared",
            project_id=project_id,
            message_id=msg["id"],
            details={"requester": requester, "goal": goal},
        )

        response_msg = Message.create(
            sender=self.name,
            recipient=requester,
            task_type="FEATURE_RESPONSE",
            context=self._base_context(msg, project_id),
            payload={"features": prioritized},
        )
        log_inter_agent_message(self.logger, response_msg, direction="SENDING")
        self.backlog.record_interaction(response_msg)
        submit(response_msg)

    def handle_manager_intervention(self, msg: Dict[str, Any]) -> None:
        """
        Handle a manager-originated free-text instruction (the website Chat
        page's `/prod <request>` command sends this via POST
        /manager/interventions, which always folds the text into
        payload["instruction"]). PM had no handler for this task_type at
        all before — the message was silently acked with no visible
        effect. Treat the instruction as a feature-request goal: generate
        + prioritize features (same pipeline as REQUEST_FEATURES), write a
        visible PM artifact, and reply to the sender.
        """
        self.logger.info(f"PMAgent: handling MANAGER_INTERVENTION {msg.get('id')}")
        payload = msg.get("payload", {}) if isinstance(msg.get("payload"), dict) else {}
        instruction = str(
            payload.get("goal")
            or payload.get("instruction")
            or payload.get("spec")
            or payload.get("message")
            or payload.get("prompt")
            or ""
        ).strip()
        requester = msg.get("sender") or "MANAGER"
        if not instruction:
            raise ValueError("MANAGER_INTERVENTION payload requires an 'instruction'.")

        features = generate_features_llm(instruction)
        prioritized = moscow_prioritize(features)
        project_id = self._resolve_project_id(msg)

        if project_id:
            add_request_to_project(project_id, {
                "type": "manager_intervention",
                "requester": requester,
                "message_id": msg.get("id", ""),
                "instruction": instruction,
                "features": features,
            })
        storage.add_project_event(
            source=self.name,
            event_type="manager_intervention_handled",
            project_id=project_id,
            message_id=msg.get("id", ""),
            details={"requester": requester, "instruction": instruction},
        )

        if write_agent_artifact is not None:
            def _bucket(label: str, items: list) -> str:
                names = [f.get("name", str(f)) if isinstance(f, dict) else str(f) for f in items]
                return f"## {label}\n\n" + ("\n".join(f"- {n}" for n in names) if names else "- none")

            body = (
                "## Manager Request\n\n"
                f"{instruction}\n\n"
                f"{_bucket('Must have', prioritized.get('must', []))}\n\n"
                f"{_bucket('Should have', prioritized.get('should', []))}\n\n"
                f"{_bucket('Could have', prioritized.get('could', []))}\n"
            )
            write_agent_artifact(
                self.name,
                title="PM Manager Request Response",
                artifact_type="feature-response",
                body=body,
                metadata={"project_id": project_id, "source": "MANAGER_INTERVENTION", "requester": requester},
                source_message_id=str(msg.get("id", "")),
                source_task_type="MANAGER_INTERVENTION",
            )

        response_msg = Message.create(
            sender=self.name,
            recipient=requester,
            task_type="FEATURE_RESPONSE",
            context=self._base_context(msg, project_id),
            payload={"features": prioritized, "instruction": instruction},
        )
        log_inter_agent_message(self.logger, response_msg, direction="SENDING")
        self.backlog.record_interaction(response_msg)
        submit(response_msg)

    def _derive_staffing_roles(self, strategy: str) -> list[str]:
        base_roles = ["Router Observability Engineer", "Product Operations Analyst"]
        text = strategy.lower()
        if "marketing" in text or "campaign" in text:
            base_roles.append("Campaign Operations Specialist")
        if "retention" in text or "customer" in text:
            base_roles.append("Customer Success Specialist")
        return base_roles

    def handle_ceo_strategy_directive(self, msg):
        self.logger.info(f"PMAgent received CEO strategy directive: {msg.get('id')}")
        payload = msg.get("payload", {})
        strategy = str(payload.get("strategy") or "")
        project_id = self._resolve_project_id(msg)
        requested_roles = self._derive_staffing_roles(strategy)

        if write_agent_artifact is not None:
            write_agent_artifact(
                self.name,
                title="PM Strategy Routing Plan",
                artifact_type="strategy-routing",
                body=(
                    "## CEO Strategy\n\n"
                    f"{strategy or 'No strategy text supplied.'}\n\n"
                    "## Staffing Request\n\n"
                    + "\n".join(f"- {role}" for role in requested_roles)
                    + "\n\n## Routed Work\n\n"
                    "- Sent staffing request to HR.\n"
                    "- Sent PM report back to CEO.\n"
                ),
                metadata={
                    "project_id": project_id,
                    "requested_roles": requested_roles,
                    "source": "CEO_STRATEGY_DIRECTIVE",
                },
                source_message_id=str(msg.get("id", "")),
                source_task_type="CEO_STRATEGY_DIRECTIVE",
            )

        hr_msg = Message.create(
            sender=self.name,
            recipient=AGENT_HR,
            task_type="TALENT_REALLOCATION",
            context={"project_id": project_id, "source_task_type": "CEO_STRATEGY_DIRECTIVE"},
            payload={
                "task": "Staff strategy execution based on CEO directive.",
                "strategy": strategy,
                "requested_roles": requested_roles,
                "requested_by": "PM",
            },
        )
        log_inter_agent_message(self.logger, hr_msg, direction="SENDING")
        self.backlog.record_interaction(hr_msg)
        submit(hr_msg)

        eng_msg = Message.create(
            sender=self.name,
            recipient=AGENT_ENGINEERING,
            task_type="IMPLEMENT_FEATURE",
            context={"project_id": project_id, "source_task_type": "CEO_STRATEGY_DIRECTIVE", "priority": "high"},
            payload={
                "feature_id": "FT-STRATEGY-001",
                "feature_name": "CEO Strategy Execution Track",
                # Previously a fixed, generic string regardless of what the
                # CEO actually decided ("Implement the first engineering
                # increment that directly supports the CEO strategy..."), so
                # Engineering built the same non-specific "increment" no
                # matter what was asked for. Now the actual strategy text
                # (which, since the CEO fix, is grounded in the real request)
                # is what Engineering is told to build.
                "spec": (
                    f"Implement the engineering work described in this CEO strategy "
                    f"directive, and report completion status/blockers back to PM:\n\n{strategy}"
                    if strategy
                    else (
                        "Implement the first engineering increment that directly supports "
                        "the CEO strategy and report completion status/blockers back to PM."
                    )
                ),
                "acceptance_criteria": [
                    "Implementation is a concrete, working increment of what the CEO strategy above describes — not a placeholder.",
                    "Implementation status is communicated back through router envelopes.",
                    "No direct non-router inter-agent communication is used.",
                ],
                "strategy": strategy,
            },
        )
        log_inter_agent_message(self.logger, eng_msg, direction="SENDING")
        self.backlog.record_interaction(eng_msg)
        submit(eng_msg)

        ceo_report = Message.create(
            sender=self.name,
            recipient=AGENT_CEO,
            task_type="PM_REPORT",
            context={"project_id": project_id, "source_task_type": "CEO_STRATEGY_DIRECTIVE"},
            payload={
                "status": "staffing_routed_to_hr",
                "requested_roles": requested_roles,
            },
        )
        log_inter_agent_message(self.logger, ceo_report, direction="SENDING")
        self.backlog.record_interaction(ceo_report)
        submit(ceo_report)

    def handle_engineering_feature_response(self, msg: Dict[str, Any]) -> None:
        """
        Handle Engineering -> PM result and close the loop back to CEO.
        """
        self.logger.info(f"PMAgent: handling FEATURE_RESPONSE {msg.get('id')}")
        payload = msg.get("payload", {}) if isinstance(msg.get("payload"), dict) else {}
        project_id = self._resolve_project_id(msg)
        status = str(payload.get("status") or msg.get("status") or "unknown")
        artifact_id = payload.get("artifact_id")

        if write_agent_artifact is not None:
            write_agent_artifact(
                self.name,
                title="PM Engineering Delivery Update",
                artifact_type="status-update",
                body=(
                    "## Engineering Response\n\n"
                    f"- Status: {status}\n"
                    f"- Artifact ID: {artifact_id or 'N/A'}\n\n"
                    "## Raw Payload\n\n"
                    "```json\n"
                    f"{json.dumps(payload, indent=2, default=str)}\n"
                    "```\n"
                ),
                metadata={
                    "project_id": project_id,
                    "source": "FEATURE_RESPONSE",
                    "engineering_status": status,
                },
                source_message_id=str(msg.get("id", "")),
                source_task_type="FEATURE_RESPONSE",
            )

        ceo_report = Message.create(
            sender=self.name,
            recipient=AGENT_CEO,
            task_type="PM_REPORT",
            context={"project_id": project_id, "source_task_type": "FEATURE_RESPONSE"},
            payload={
                "status": "engineering_update_received",
                "engineering_status": status,
                "engineering_artifact_id": artifact_id,
                "engineering_payload": payload,
            },
        )
        log_inter_agent_message(self.logger, ceo_report, direction="SENDING")
        self.backlog.record_interaction(ceo_report)
        submit(ceo_report)
