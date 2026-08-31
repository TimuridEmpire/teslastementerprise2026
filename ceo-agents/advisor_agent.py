from typing import Any, Dict

from enterprise_router.agent_artifacts import write_agent_artifact

from agent_logger import get_agent_logger, log_inter_agent_message
from agent_transport import AGENT_CEO, make_envelope, submit
from enterprise_router_client import EnterpriseRouterClient
from message_schema import EnvelopeInput, Message

from thread_safe_agent import ThreadSafeAgentMixin


class AdvisorAgent(ThreadSafeAgentMixin):
    """
    Advisor Agent Class
    Responsible for auditing the CEO's decisions and ensuring all actions 
    align with the company's established strategic guidelines.
    """
    
    def __init__(self, name="Strategic Advisor", core_strategy=""):
        super().__init__()
        self.name = name
        self.core_strategy = core_strategy
        self.logger = get_agent_logger(self.name)
        preview = self.core_strategy[:50] if self.core_strategy else ""
        self.logger.info(
            "%s initialized with core strategy: %r",
            self.name,
            f"{preview}..." if len(self.core_strategy) > 50 else self.core_strategy,
        )

    def evaluate_ceo_decision(self, ceo_proposal_message: EnvelopeInput):
        """
        Takes a JSON message from the CEO, evaluates the payload against the 
        core strategy, and returns an advisory response message.
        """
        with self._agent_lock:
            return self._evaluate_ceo_decision_unlocked(ceo_proposal_message)

    def _evaluate_ceo_decision_unlocked(self, ceo_proposal_message: EnvelopeInput) -> Dict[str, Any]:
        self.logger.info("Received proposal from CEO for strategic review.")
        
        # 1. Log the incoming message from the CEO
        log_inter_agent_message(self.logger, ceo_proposal_message, direction="RECEIVING")
        
        proposal = (
            ceo_proposal_message
            if isinstance(ceo_proposal_message, Message)
            else Message.from_dict(ceo_proposal_message)
        )
        proposed_action = proposal.payload
        task_type = proposal.task_type or "UNKNOWN"
        
        # 2. Perform the evaluation (Simulated AI Logic)
        # In a real app, you would pass the self.core_strategy and the proposed_action to an LLM prompt here.
        is_aligned = True
        feedback = "Proposal strongly aligns with Q1/Q2 revenue targets."
        
        # Example of catching a strategic drift:
        if "manufactur" in str(proposed_action).lower() and "software" in self.core_strategy.lower():
            is_aligned = False
            feedback = "WARNING: Proposed hardware manufacturing violates the core software focus strategy."

        result_payload = {
            "is_aligned": is_aligned,
            "assessment": feedback,
            "recommended_action": "PROCEED" if is_aligned else "REVISE",
        }
        artifact = write_agent_artifact(
            self.name,
            title="Strategic review",
            body=(
                f"## Assessment\n\n{feedback}\n\n"
                f"## Recommendation\n\n{result_payload['recommended_action']}\n\n"
                "## Proposal\n\n```json\n"
                + __import__("json").dumps(proposed_action, indent=2, default=str)
                + "\n```"
            ),
            artifact_type="strategy_review",
            metadata={
                "source": "advisor_agent",
                "original_task": task_type,
                "is_aligned": is_aligned,
            },
            source_message_id=proposal.id,
            source_task_type=task_type,
        )
        result_payload["artifact_id"] = artifact.get("artifact_id")

        response_task_type = (
            "STRATEGY_REVIEW_RESULT"
            if (proposal.sender or AGENT_CEO) == AGENT_CEO
            else "PM_REPORT"
        )
        advisory_response = make_envelope(
            sender=self.name,
            recipient=proposal.sender or AGENT_CEO,
            task_type=response_task_type,
            context={
                "original_task": task_type,
                "review_cycle": "pre-execution",
            },
            payload=result_payload,
            status="done",
        )

        log_inter_agent_message(self.logger, advisory_response, direction="SENDING")
        submit(advisory_response)

        return advisory_response

    def on_bus_envelope(self, envelope: Dict[str, Any]) -> Any:
        task = (envelope.get("task_type") or "").strip()
        if task in (
            "STRATEGY_REVIEW_REQUEST",
            "CEO_PROPOSAL_FOR_REVIEW",
        ) or task.endswith("_FOR_REVIEW"):
            return self.evaluate_ceo_decision(envelope)
        return {
            "ok": True,
            "agent": self.name,
            "task_type": task or "UNKNOWN",
            "note": "Advisor acknowledged; no review handler for this task_type.",
        }

    def process_one_router_message(
        self,
        *,
        router_client: EnterpriseRouterClient | None = None,
        recipient: str | None = None,
    ) -> bool:
        """Fetch, process, and ack/nack one Advisor message from the enterprise router."""
        target = recipient or self.name
        client = router_client or EnterpriseRouterClient.from_env(agent_name=target)
        envelope = client.fetch_next(target)
        if envelope is None:
            return False

        message_id = str(envelope.get("id", ""))
        try:
            self.on_bus_envelope(envelope)
        except Exception as exc:
            client.nack_message(message_id, target, reason=str(exc))
            return True

        client.ack_message(message_id, target)
        return True
