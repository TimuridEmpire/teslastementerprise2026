import uuid
import datetime

from agents.advisor_agent import AdvisorAgent

def run_strategy_simulation():
    print("--- Starting Executive Board Simulation ---")
    
    # 1. Initialize the Advisor with the company's strategy
    #TODO: Change strategy to be more specific towards Kanosei's goals
    #TODO: Add more specific strategies for the advisor to evaluate against
    company_strategy = "We are Kanosei, a company focused strictly on software. We do not manufacture hardware."
    board_advisor = AdvisorAgent(name="Advisor", core_strategy=company_strategy)
    
    # 2. The CEO formulates a plan and wraps it in the strict JSON schema
    ceo_proposal = {
        "id": f"req-{uuid.uuid4().hex[:6]}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "sender": "CEO",
        "recipient": "Advisor",
        "task_type": "PROPOSE_Q2_ROADMAP",
        "context": {
            "quarter": "Q2",
            "year": 2026
        },
        "payload": {
            "business_goal": "Increase revenue by 15%",
            "initiatives": [
                "Expand enterprise software tier",
                "Start manufacturing proprietary servers for clients" # <-- Strategic drift!
            ]
        },
        "status": "pending",
        "error": ""
    }
    
    # 3. The Advisor cross-references the CEO's plan
    print("\n[SYSTEM] CEO is submitting roadmap to Advisor for review...")
    advisory_feedback = board_advisor.evaluate_ceo_decision(ceo_proposal)
    
    # 4. The CEO acts on the feedback (Checking the structured payload)
    print("\n[SYSTEM] CEO processing Advisor feedback...")
    if advisory_feedback["payload"]["is_aligned"]:
        print("CEO: Plan approved. Broadcasting to PM and Finance.")
    else:
        print(f"CEO: Plan rejected. Revising based on feedback: {advisory_feedback['payload']['assessment']}")

    print("\n--- Simulation Complete ---")

if __name__ == "__main__":
    run_strategy_simulation()
