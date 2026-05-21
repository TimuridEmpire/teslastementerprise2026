from agent_logger import get_agent_logger, log_inter_agent_message

def run_test():
    print("--- Starting Messaging Test ---")
    
    # 1. Initialize the logger
    ceo_logger = get_agent_logger("CEO_Agent")

    # 2. Define the message payload
    ceo_to_pm_message = {
      "id": "req-001",
      "timestamp": "2026-03-01T10:00:00Z",
      "sender": "CEO",
      "recipient": "PM",
      "task_type": "DEFINE_Q2_ROADMAP",
      "context": {
        "quarter": "Q2",
        "year": 2026
      },
      "payload": {
        "business_goal": "Increase SaaS revenue by 15%",
        "constraints": [
          "Engineering capacity limited to 3 major features",
          "Focus on small-business customers"
        ]
      },
      "status": "pending",
      "error": ""
    }

    # 3. Log the message
    log_inter_agent_message(ceo_logger, ceo_to_pm_message, direction="SENDING")
    print("--- Test Complete ---")

if __name__ == "__main__":
    run_test()
