# CEO Agent Class
# The CEO agent will interact with other agentsto gather information and make informed decisions
# This acts as the blueprint for ther CEO agent, which will be implemented in the main application

# Import the logger from your custom logging file
import datetime
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import requests
from agent_logger import get_agent_logger

from thread_safe_agent import ThreadSafeAgentMixin

if TYPE_CHECKING:
    from ceo_distribution_tokens import CeoDistributionTokenRegistry


class CeoAgent(ThreadSafeAgentMixin):
    """
    CEO Agent Class
    Oversees the company by gathering info from departments and 
    using Mistral (via Docker) to make strategic decisions.
    """
    
    def __init__(
        self,
        name="CEO",
        distribution_registry: Optional["CeoDistributionTokenRegistry"] = None,
    ):
        super().__init__()
        self.name = name
        self.logger = get_agent_logger(self.name)
        self.distribution_registry = distribution_registry
        self.legal_compliance_subagent = "Legal Compliance Agent"
        self.children_nearby_detected = False
        self.enforce_local_audio_only = True
        self.disallow_external_audio_storage = True
        # Ollama API endpoints for Mistral.
        self.ollama_chat_url = "http://localhost:11434/api/chat"
        self.ollama_generate_url = "http://localhost:11434/api/generate"
        self.model_name = "mistral"
        self.chat_history: List[Dict[str, str]] = []
        self.metrics: Dict[str, Any] = {
            "tasks_per_agent": {},
            "success_count": 0,
            "failure_count": 0,
            "last_cycle_duration_ms": None,
            "last_cycle_started_at": None,
        }
        self.logger.info(f"{self.name} Agent initialized and linked to Docker.")

    def update_environment_safety_signal(self, *, children_nearby: bool) -> None:
        """Persist latest child-safety signal from local sensors/microphones."""
        with self._agent_lock:
            self.children_nearby_detected = bool(children_nearby)
            self.logger.info(
                "Updated environment safety signal: children_nearby=%s",
                self.children_nearby_detected,
            )

    def register_distribution_scenario(
        self, scenario_id: str, *, cost_per_send: int = 1
    ) -> None:
        """Define a governed distribution lane (only the executive may call)."""
        with self._agent_lock:
            self._enforce_child_safety_gate_unlocked(
                operation="register_distribution_scenario"
            )
            if not self.distribution_registry:
                raise RuntimeError("CeoAgent has no distribution_registry attached.")
            self.distribution_registry.register_scenario(
                scenario_id,
                cost_per_send=cost_per_send,
                acting_executive=self.name,
            )
            self.logger.info(
                "Registered distribution scenario %r (cost_per_send=%s)",
                scenario_id,
                cost_per_send,
            )

    def mint_distribution_tokens(
        self, scenario_id: str, quantity: int, holder: Optional[str] = None
    ) -> None:
        """Create supply for a scenario and credit a holder (defaults to this agent)."""
        with self._agent_lock:
            self._enforce_child_safety_gate_unlocked(operation="mint_distribution_tokens")
            if not self.distribution_registry:
                raise RuntimeError("CeoAgent has no distribution_registry attached.")
            self.distribution_registry.mint(
                scenario_id,
                quantity,
                holder or self.name,
                acting_executive=self.name,
            )
            self.logger.info(
                "Minted %s token(s) for scenario %r to holder %r",
                quantity,
                scenario_id,
                holder or self.name,
            )

    def assign_distribution_tokens(
        self,
        scenario_id: str,
        to_holder: str,
        quantity: int,
        *,
        from_holder: Optional[str] = None,
    ) -> None:
        """Move tokens between holders (typically from CEO to a department agent)."""
        with self._agent_lock:
            self._enforce_child_safety_gate_unlocked(
                operation="assign_distribution_tokens"
            )
            if not self.distribution_registry:
                raise RuntimeError("CeoAgent has no distribution_registry attached.")
            self.distribution_registry.transfer(
                scenario_id,
                from_holder or self.name,
                to_holder,
                quantity,
                acting_executive=self.name,
            )
            self.logger.info(
                "Assigned %s token(s) for scenario %r from %r to %r",
                quantity,
                scenario_id,
                from_holder or self.name,
                to_holder,
            )

    def talk_to_engine(self, prompt):
        """Bridge to the Mistral model in Docker."""
        with self._agent_lock:
            return self._talk_to_engine_unlocked(prompt)

    def chat_with_engine(self, user_message: str) -> Any:
        """Chat-style call for CEO conversations using Ollama /api/chat."""
        with self._agent_lock:
            return self._chat_with_engine_unlocked(user_message)

    def gather_information(self, subordinate_agents: List[str]):
        """
        Restored: Compiles reports from all departments.
        Later, this will involve reading actual files or agent outputs.
        """
        with self._agent_lock:
            return self._gather_information_unlocked(subordinate_agents)

    def make_strategic_decision(self, data):
        """Uses Mistral to analyze gathered data and provide a strategy."""
        with self._agent_lock:
            return self._make_strategic_decision_unlocked(data)

    def get_metrics(self) -> Dict[str, Any]:
        """Return a safe snapshot of CEO runtime metrics."""
        with self._agent_lock:
            return self._metrics_snapshot_unlocked()

    def execute_reasoning_loop(
        self,
        message: str,
        subordinate_agents: Optional[List[str]] = None,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Chat-like CEO flow:
        - Receives a CEO request (user message)
        - Delegates simulated tasks to subordinate agents
        - Produces final summary
        - Tracks success/failure + end-to-end cycle timing
        """
        with self._agent_lock:
            started_at = datetime.datetime.now(datetime.timezone.utc)
            self.metrics["last_cycle_started_at"] = started_at.strftime("%Y-%m-%dT%H:%M:%SZ")
            context = context or {}
            result: Dict[str, Any]
            try:
                self._refresh_child_signal_from_context_unlocked(context)
                reroute = self._enforce_child_safety_gate_unlocked(
                    operation="execute_reasoning_loop"
                )
                if reroute:
                    self._record_failure_unlocked()
                    result = {
                        "ok": False,
                        "agent": self.name,
                        "message": message,
                        "final_summary": "Request rerouted due to child-safety policy.",
                        "reroute": reroute,
                    }
                    return result
                self._enforce_local_audio_privacy_boundary_unlocked(
                    context.get("audio_policy")
                    if isinstance(context.get("audio_policy"), dict)
                    else None
                )

                departments = subordinate_agents or [
                    "PM Agent",
                    "Engineering Agent",
                    "Marketing Agent",
                    "HR Agent",
                    "Sales Agent",
                    "Finance Agent",
                ]
                reports = self._gather_information_unlocked(departments)
                strategic_decision = self._make_strategic_decision_unlocked(reports)
                final_summary = self._chat_with_engine_unlocked(
                    (
                        "Create a concise executive summary from the CEO request, department "
                        f"reports, and strategic decision.\n"
                        f"CEO request: {message}\n"
                        f"Department reports: {reports}\n"
                        f"Strategic decision: {strategic_decision}"
                    )
                )
                self._record_success_unlocked()
                result = {
                    "ok": True,
                    "id": f"ceo-{uuid.uuid4().hex[:8]}",
                    "agent": self.name,
                    "message": message,
                    "department_reports": reports,
                    "strategic_decision": strategic_decision,
                    "final_summary": final_summary,
                }
                return result
            except Exception as exc:
                self._record_failure_unlocked()
                self.logger.exception("CEO reasoning loop failed: %s", exc)
                result = {
                    "ok": False,
                    "agent": self.name,
                    "message": message,
                    "final_summary": f"Failed to complete CEO reasoning loop: {exc}",
                }
                return result
            finally:
                finished_at = datetime.datetime.now(datetime.timezone.utc)
                elapsed_ms = int((finished_at - started_at).total_seconds() * 1000)
                self.metrics["last_cycle_duration_ms"] = elapsed_ms
                if "result" in locals():
                    result["metrics"] = self._metrics_snapshot_unlocked()

    def _talk_to_engine_unlocked(self, prompt: str) -> Any:
        """Same as ``talk_to_engine`` without taking ``_agent_lock`` (for internal use under lock)."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }
        try:
            response = requests.post(self.ollama_generate_url, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                return "Strategic Link Error: invalid response payload from Mistral."
            return data.get("response")
        except requests.RequestException as e:
            return f"Strategic Link Error: Ensure Docker is running. {e}"
        except ValueError as e:
            return f"Strategic Link Error: invalid JSON payload returned. {e}"

    def _chat_with_engine_unlocked(self, user_message: str) -> Any:
        self.chat_history.append({"role": "user", "content": user_message})
        payload = {
            "model": self.model_name,
            "messages": self.chat_history,
            "stream": False,
        }
        try:
            response = requests.post(self.ollama_chat_url, json=payload, timeout=25)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                return "Strategic Link Error: invalid chat response payload from Mistral."
            message_block = data.get("message")
            if isinstance(message_block, dict):
                assistant_reply = str(message_block.get("content") or "").strip()
            else:
                assistant_reply = str(data.get("response") or "").strip()
            if not assistant_reply:
                assistant_reply = "No response returned by Mistral chat endpoint."
            self.chat_history.append({"role": "assistant", "content": assistant_reply})
            return assistant_reply
        except requests.RequestException as e:
            err = f"Strategic Link Error: Ensure Docker is running. {e}"
            self.chat_history.append({"role": "assistant", "content": err})
            return err
        except ValueError as e:
            err = f"Strategic Link Error: invalid JSON payload returned. {e}"
            self.chat_history.append({"role": "assistant", "content": err})
            return err

    def oversee_company(self, subordinate_agents, context: Optional[Dict[str, Any]] = None):
        """The main workflow loop."""
        with self._agent_lock:
            context = context or {}
            self._refresh_child_signal_from_context_unlocked(context)
            reroute = self._enforce_child_safety_gate_unlocked(operation="oversee_company")
            if reroute:
                return reroute
            self._enforce_local_audio_privacy_boundary_unlocked(
                context.get("audio_policy")
                if isinstance(context.get("audio_policy"), dict)
                else None
            )
            self.logger.info("Starting company oversight cycle.")
            data = self._gather_information_unlocked(subordinate_agents)
            decision = self._make_strategic_decision_unlocked(data)
            return decision

    def _refresh_child_signal_from_context_unlocked(self, context: Dict[str, Any]) -> None:
        if "children_nearby" in context:
            self.children_nearby_detected = bool(context.get("children_nearby"))
        elif "children_detected" in context:
            self.children_nearby_detected = bool(context.get("children_detected"))
        elif "nearby_children_count" in context:
            try:
                self.children_nearby_detected = int(context.get("nearby_children_count", 0)) > 0
            except (TypeError, ValueError):
                self.children_nearby_detected = False

    def _route_to_legal_compliance_unlocked(self, operation: str) -> Dict[str, Any]:
        self.logger.warning(
            "Child-safety gate triggered before %s. Rerouting to %s.",
            operation,
            self.legal_compliance_subagent,
        )
        return {
            "ok": False,
            "agent": self.name,
            "rerouted_to": self.legal_compliance_subagent,
            "reason": "children_nearby_detected",
            "required_action": "Apply child protection compliance workflow before allocation/decision.",
            "blocked_operation": operation,
        }

    def _enforce_child_safety_gate_unlocked(self, operation: str) -> Optional[Dict[str, Any]]:
        """
        Rule #1: if children are nearby, reroute to legal compliance
        before strategic/resource allocation actions.
        """
        if self.children_nearby_detected:
            reroute = self._route_to_legal_compliance_unlocked(operation)
            if operation in {
                "register_distribution_scenario",
                "mint_distribution_tokens",
                "assign_distribution_tokens",
            }:
                raise PermissionError(
                    f"{operation} blocked by child-safety gate; rerouted to "
                    f"{self.legal_compliance_subagent}."
                )
            return reroute
        return None

    def _enforce_local_audio_privacy_boundary_unlocked(
        self, audio_policy: Optional[Dict[str, Any]]
    ) -> None:
        """
        Rule #2: analyzed audio must stay local and must not be stored externally.
        """
        if not audio_policy:
            return

        processed_locally = bool(audio_policy.get("processed_locally"))
        stored_externally = bool(audio_policy.get("stored_externally"))

        if self.enforce_local_audio_only and not processed_locally:
            raise PermissionError(
                "Audio privacy boundary violation: audio analysis must run on the local device."
            )
        if self.disallow_external_audio_storage and stored_externally:
            raise PermissionError(
                "Audio privacy boundary violation: external audio storage is not allowed."
            )
        self.logger.info(
            "Audio privacy boundary validated (local-only processing, no external storage)."
        )

    def _gather_information_unlocked(self, subordinate_agents: List[str]) -> List[str]:
        self.logger.info("Initiating information gathering from departments...")
        for agent in subordinate_agents:
            self._record_task_for_agent_unlocked(agent)
        gathered_data = [
            f"Status report from {agent}: All systems operational."
            for agent in subordinate_agents
        ]
        self.logger.info(
            f"Successfully gathered {len(gathered_data)} department reports."
        )
        return gathered_data

    def _make_strategic_decision_unlocked(self, data) -> Any:
        self.logger.info("Sending data to Mistral for strategic analysis...")
        prompt = (
            f"You are the CEO. Based on these department reports, "
            f"identify the single most important strategic priority for the next quarter: {data}"
        )
        decision = self._talk_to_engine_unlocked(prompt)
        self.logger.warning(f"Strategic Decision Executed: {decision}")
        return decision

    def _record_task_for_agent_unlocked(self, agent_name: str) -> None:
        safe_name = str(agent_name or "unknown")
        tasks = self.metrics.get("tasks_per_agent")
        if not isinstance(tasks, dict):
            tasks = {}
            self.metrics["tasks_per_agent"] = tasks
        tasks[safe_name] = int(tasks.get(safe_name, 0)) + 1

    def _record_success_unlocked(self) -> None:
        self.metrics["success_count"] = int(self.metrics.get("success_count", 0)) + 1

    def _record_failure_unlocked(self) -> None:
        self.metrics["failure_count"] = int(self.metrics.get("failure_count", 0)) + 1

    def _metrics_snapshot_unlocked(self) -> Dict[str, Any]:
        tasks = self.metrics.get("tasks_per_agent")
        safe_tasks = dict(tasks) if isinstance(tasks, dict) else {}
        return {
            "tasks_per_agent": safe_tasks,
            "success_count": int(self.metrics.get("success_count", 0)),
            "failure_count": int(self.metrics.get("failure_count", 0)),
            "last_cycle_duration_ms": self.metrics.get("last_cycle_duration_ms"),
            "last_cycle_started_at": self.metrics.get("last_cycle_started_at"),
        }

    def on_bus_envelope(self, envelope: Dict[str, Any]) -> Any:
        """
        Serialized entry for ``MessageBus`` delivery. Extend with task_type routing as needed.
        """
        task = (envelope.get("task_type") or "").strip()
        payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}

        if task == "CEO_STRATEGIC_CYCLE":
            departments = payload.get("departments") or payload.get("subordinate_agents")
            if not isinstance(departments, list):
                departments = []
            names = [str(x) for x in departments]
            return self.oversee_company(names, context=payload)

        if task == "CEO_ENVIRONMENT_SIGNAL":
            self.update_environment_safety_signal(
                children_nearby=bool(payload.get("children_nearby") or payload.get("children_detected"))
            )
            return {
                "ok": True,
                "agent": self.name,
                "task_type": task,
                "children_nearby_detected": self.children_nearby_detected,
            }

        if task == "CEO_PING":
            return {"ok": True, "agent": self.name, "task_type": task}

        if task == "CEO_GATHER_ONLY":
            departments = payload.get("departments") or []
            if not isinstance(departments, list):
                departments = []
            return self.gather_information([str(x) for x in departments])

        if task == "CEO_CHAT":
            user_message = str(payload.get("message") or payload.get("prompt") or "")
            reply = self.chat_with_engine(user_message)
            return {
                "ok": True,
                "agent": self.name,
                "task_type": task,
                "reply": reply,
                "history_length": len(self.chat_history),
            }

        if task == "CEO_REASONING_LOOP":
            departments = payload.get("departments") or payload.get("subordinate_agents") or []
            if not isinstance(departments, list):
                departments = []
            message = str(payload.get("message") or payload.get("prompt") or "")
            return self.execute_reasoning_loop(
                message,
                [str(x) for x in departments] if departments else None,
                context=payload,
            )

        if task == "CEO_METRICS":
            return {
                "ok": True,
                "agent": self.name,
                "task_type": task,
                "metrics": self.get_metrics(),
            }

        return {
            "ok": True,
            "agent": self.name,
            "task_type": task or "UNKNOWN",
            "note": "No specific handler; envelope acknowledged.",
        }

if __name__ == "__main__":
    # 1. Instantiate
    my_ceo = CeoAgent(name="CEO")
    
    # 2. Define Departments
    company_agents = [
        "PM Agent", "Engineering Agent", "Marketing Agent", 
        "HR Agent", "Sales Agent", "Finance Agent", "UI Agent"
    ]
    
    # 3. Execute Workflow
    result = my_ceo.oversee_company(company_agents)
    
    print("-" * 30)
    print(f"FINAL CEO STRATEGY FROM MISTRAL:\n{result}")
    print("-" * 30)
