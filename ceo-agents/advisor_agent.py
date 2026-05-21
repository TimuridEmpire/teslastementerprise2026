import uuid
import datetime
from typing import Any, Dict

from agent_logger import get_agent_logger, log_inter_agent_message

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

    def evaluate_ceo_decision(self, ceo_proposal_message):
        """
        Takes a JSON message from the CEO, evaluates the payload against the 
        core strategy, and returns an advisory response message.
        """
        with self._agent_lock:
            return self._evaluate_ceo_decision_unlocked(ceo_proposal_message)

    def _evaluate_ceo_decision_unlocked(self, ceo_proposal_message: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("Received proposal from CEO for strategic review.")
        
        # 1. Log the incoming message from the CEO
        log_inter_agent_message(self.logger, ceo_proposal_message, direction="RECEIVING")
        
        # Extract the CEO's proposed payload to analyze
        proposed_action = ceo_proposal_message.get("payload", {})
        task_type = ceo_proposal_message.get("task_type", "UNKNOWN")
        
        # 2. Perform the evaluation (Simulated AI Logic)
        # In a real app, you would pass the self.core_strategy and the proposed_action to an LLM prompt here.
        is_aligned = True
        feedback = "Proposal strongly aligns with Q1/Q2 revenue targets."
        
        # Example of catching a strategic drift:
        if "manufactur" in str(proposed_action).lower() and "software" in self.core_strategy.lower():
            is_aligned = False
            feedback = "WARNING: Proposed hardware manufacturing violates the core software focus strategy."

        # 3. Construct the Advisor's response using the strict JSON schema
        advisory_response = {
            "id": f"adv-{uuid.uuid4().hex[:6]}",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "sender": self.name,
            "recipient": ceo_proposal_message.get("sender", "CEO"),
            "task_type": "STRATEGY_REVIEW_RESULT",
            "context": {
                "original_task": task_type,
                "review_cycle": "pre-execution"
            },
            "payload": {
                "is_aligned": is_aligned,
                "assessment": feedback,
                "recommended_action": "PROCEED" if is_aligned else "REVISE"
            },
            "status": "done",
            "error": ""
        }
        
        # 4. Log the outgoing feedback
        log_inter_agent_message(self.logger, advisory_response, direction="SENDING")
        
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
