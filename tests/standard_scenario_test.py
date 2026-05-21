import uuid
import time
from datetime import datetime, timezone

# Import the core infrastructure
from message_bus import MessageBus
from inter_agent_mongo import inter_agent_store_from_env
from ceo_distribution_tokens import CeoDistributionTokenRegistry

def generate_envelope(sender: str, recipient: str, task_type: str, payload: dict, scenario: str = "STANDARD_DELEGATION") -> dict:
    """Helper to generate our strict JSON schema envelope, now with dynamic scenarios."""
    return {
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "sender": sender,
        "recipient": recipient,
        "task_type": task_type,
        "context": {
            "project": "Project Tesla",
            "distribution_scenario": scenario 
        },
        "payload": payload,
        "status": "pending",
        "error": ""
    }

def run_launch_simulation():
    print("\n --- Booting Enterprise Multi-Agent Simulation: Project Tesla --- \n")

    # 1. Initialize the Token Registry (The Central Bank)
    token_registry = CeoDistributionTokenRegistry(executive_name="CEO")

    # --- CEO TOKEN ECONOMY SETUP ---
    print("[SYSTEM] CEO is establishing the internal token economy...")
    
    # Register and distribute STANDARD_DELEGATION (Total Supply: 130)
    token_registry.register_scenario("STANDARD_DELEGATION", cost_per_send=1, acting_executive="CEO")
    token_registry.mint("STANDARD_DELEGATION", 130, "CEO", acting_executive="CEO") # Mint all 130 to CEO first
    
    # Transfer tokens from CEO to respective departments based on README policy
    allocations = {
        "PM": 25,
        "Engineering": 20,
        "Marketing": 15,
        "HR": 10,
        "Sales": 10,
        "Finance": 10
        # CEO retains the remaining 30
    }
    for agent, amount in allocations.items():
        token_registry.transfer("STANDARD_DELEGATION", "CEO", agent, amount, acting_executive="CEO")

    # Register and distribute EXECUTIVE_BROADCAST (Total Supply: 15, Cost: 3)
    token_registry.register_scenario("EXECUTIVE_BROADCAST", cost_per_send=3, acting_executive="CEO")
    token_registry.mint("EXECUTIVE_BROADCAST", 15, "CEO", acting_executive="CEO")
    token_registry.transfer("EXECUTIVE_BROADCAST", "CEO", "PM", 3, acting_executive="CEO") # PM gets 1 broadcast

    # 2. Initialize Infrastructure (Wiring the registry into the bus)
    mongo_store = inter_agent_store_from_env(mirror_sqlite=True)
    bus = MessageBus(
        json_log_path="tesla_audit.jsonl", 
        distribution_tokens=token_registry, 
        enforce_distribution_tokens=True
    )
    
    # 3. Define Sub-Agent Handlers (The Receivers)
    def pm_handler(message):
        reply = generate_envelope("PM", "CEO", "SPECS_COMPLETE", {"specs": "MoSCoW complete.", "status": "Ready for Eng"})
        bus.send(reply)

    def eng_handler(message):
        reply = generate_envelope("Engineering", "CEO", "TIMELINE_ESTIMATE", {"timeline": "6 weeks", "blocker": "Need ML Contractors"})
        bus.send(reply)

    def hr_handler(message):
        reply = generate_envelope("HR", "Finance", "RESOURCE_COSTS", {"role": "ML Contractors (x2)", "monthly_cost": 30000})
        bus.send(reply)
        reply_to_ceo = generate_envelope("HR", "CEO", "HIRING_PLAN", {"status": "Sourcing on LinkedIn", "eta": "14 days"})
        bus.send(reply_to_ceo)

    def marketing_handler(message):
        reply = generate_envelope("Marketing", "Finance", "AD_SPEND", {"cac_estimate": 150, "total_budget_request": 45000})
        bus.send(reply)
        reply_to_ceo = generate_envelope("Marketing", "CEO", "CAMPAIGN_READY", {"strategy": "Multi-channel B2B SEO + Ads"})
        bus.send(reply_to_ceo)

    def sales_handler(message):
        reply = generate_envelope("Sales", "CEO", "PIPELINE_PROJECTION", {"target_accounts": 20, "estimated_arr": 250000})
        bus.send(reply)

    def finance_handler(message):
        task = message.get("task_type")
        if task == "FINANCE_DIRECTIVE":
            print("[SYSTEM] Finance acknowledging base $150k budget constraint.")
        elif task in ["RESOURCE_COSTS", "AD_SPEND"]:
            reply = generate_envelope("Finance", "CEO", "ROI_FORECAST", {"projected_roi": "22%", "burn_rate": "Acceptable"})
            bus.send(reply)

    # 4. Register Agents to the Bus
    bus.register("PM", pm_handler)
    bus.register("Engineering", eng_handler)
    bus.register("HR", hr_handler)
    bus.register("Marketing", marketing_handler)
    bus.register("Sales", sales_handler)
    bus.register("Finance", finance_handler)

    # 5. The CEO Initiates the Project
    print("\n[CEO] Initiating Project Tesla. Broadcasting directives to executive team...\n")
    
    ceo_directives = [
        ("Finance", "FINANCE_DIRECTIVE", {"budget_limit": 150000, "directive": "Calculate strict ROI."}),
        ("PM", "DRAFT_SPECS", {"directive": "Draft MVP specs using MoSCoW method."}),
        ("Engineering", "TECHNICAL_EVAL", {"directive": "Evaluate feasibility and timeline."}),
        ("HR", "RECRUIT_TALENT", {"directive": "Recruit 2 ML contractors immediately."}),
        ("Marketing", "DRAFT_CAMPAIGN", {"directive": "Design pre-launch campaign, estimate CAC."}),
        ("Sales", "PREP_PIPELINE", {"directive": "Prepare pitches for top 20 accounts."})
    ]

    for recipient, task, payload in ceo_directives:
        # Defaults to STANDARD_DELEGATION, costing the CEO 1 token per send
        envelope = generate_envelope("CEO", recipient, task, payload)
        bus.send(envelope)
        time.sleep(0.1) 

    # 6. CEO Final Decision (Using the expensive Broadcast token)
    print("\n[CEO] Reviewing incoming departmental data...")
    time.sleep(1)
    print("[CEO] Minimum ROI of 20% met. Technical roadmap validated. Pipeline confirmed.")
    
    # The CEO uses their EXECUTIVE_BROADCAST token for the final company-wide push
    final_decision = generate_envelope(
        sender="CEO", 
        recipient="Broadcast", 
        task_type="EXECUTIVE_DECISION", 
        payload={"decision": "GO", "notes": "Project Tesla is approved."},
        scenario="EXECUTIVE_BROADCAST"
    )
    bus.send(final_decision)
    
    # 7. Print Final Balances to prove the economy worked
    print("\n--- Final Token Balances ---")
    balances = token_registry.snapshot_balances()
    for (holder, scenario), amount in balances.items():
        print(f"{holder} ({scenario}): {amount} tokens remaining")

    print("\n --- Simulation Complete. Audit logs safely persisted. --- ")

if __name__ == "__main__":
    run_launch_simulation()