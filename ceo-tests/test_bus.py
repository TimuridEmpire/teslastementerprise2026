# test_bus.py — Message bus integration test (same envelope schema as test_advisor / test_messaging)
import os
import uuid
import datetime

from agent_backlog import AgentBacklog
from agent_logger import log_inter_agent_message
from agents.advisor_agent import AdvisorAgent
from agents.ceo_agent import CeoAgent
from message_bus import MessageBus


def run_bus_simulation():
    print("--- Starting Message Bus Simulation ---")

    here = os.path.dirname(os.path.abspath(__file__))
    bus = MessageBus(
        backlog=AgentBacklog(os.path.join(here, "test_bus_backlog.db")),
        json_log_path=os.path.join(here, "fixtures", "test_bus_messages.jsonl"),
    )

    # Mirrors test_advisor.py strategy so AdvisorAgent rules apply predictably
    company_strategy = (
        "We are Kanosei, a company focused strictly on software. We do not manufacture hardware."
    )
    board_advisor = AdvisorAgent(name="Advisor", core_strategy=company_strategy)
    ceo_agent = CeoAgent(name="CEO")

    # Bus handlers must accept a single envelope dict. CeoAgent.oversee_company expects
    # a list of department names — do not register it directly on the bus.

    def ceo_inbox(envelope):
        """CEO receives advisory replies (and any other mail) as standardized envelopes."""
        log_inter_agent_message(ceo_agent.logger, envelope, direction="RECEIVING")
        payload = envelope.get("payload", {})
        print("\n[SYSTEM] CEO inbox: processing message from bus...")
        if envelope.get("task_type") == "STRATEGY_REVIEW_RESULT":
            if payload.get("is_aligned"):
                print("CEO: Plan approved. Broadcasting to PM and Finance.")
            else:
                print(f"CEO: Plan rejected. Revising based on: {payload.get('assessment', '')}")
        else:
            print(f"CEO: Noted message task_type={envelope.get('task_type')!r}")

    bus.register("Advisor", board_advisor.evaluate_ceo_decision)
    bus.register("CEO", ceo_inbox)

    ceo_proposal = {
        "id": f"req-{uuid.uuid4().hex[:6]}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sender": "CEO",
        "recipient": "Advisor",
        "task_type": "PROPOSE_NEW_FEATURE",
        "context": {"platform": "Spotify"},
        "payload": {
            "business_goal": "Increase user engagement",
            "feature": "AI kids voice detection for auto-filtering",
        },
        "status": "pending",
        "error": "",
    }

    print("\n[SYSTEM] CEO is sending a proposal to the bus (recipient=Advisor)...")
    advisory_reply = bus.send(ceo_proposal)

    if advisory_reply:
        print("\n[SYSTEM] Forwarding Advisor reply to CEO via bus (recipient=CEO)...")
        bus.send(advisory_reply)
    else:
        print("\n[SYSTEM] No advisory reply returned; check bus handler registration.")

    print("\n--- Simulation Complete ---")


if __name__ == "__main__":
    run_bus_simulation()
