from agent_logger import get_agent_logger, log_inter_agent_message
from agent_transport import AGENT_CEO, AGENT_PM, submit
from message_schema import Message


def run_test():
    print("--- Starting Messaging Test ---")

    ceo_logger = get_agent_logger("CEO_Agent")

    ceo_to_pm_message = Message.create(
        sender=AGENT_CEO,
        recipient=AGENT_PM,
        task_type="DEFINE_Q2_ROADMAP",
        context={
            "quarter": "Q2",
            "year": 2026,
        },
        payload={
            "business_goal": "Increase SaaS revenue by 15%",
            "constraints": [
                "Engineering capacity limited to 3 major features",
                "Focus on small-business customers",
            ],
        },
    )

    log_inter_agent_message(ceo_logger, ceo_to_pm_message, direction="SENDING")

    try:
        mid = submit(ceo_to_pm_message)
        print(f"Routed message id={mid}")
    except RuntimeError as exc:
        print(f"Router not configured (log-only mode): {exc}")

    print("--- Test Complete ---")


if __name__ == "__main__":
    run_test()
