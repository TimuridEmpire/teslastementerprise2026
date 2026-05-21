"""
Insert a test PM → Engineering message via the enterprise router (or legacy Mongo).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent_transport import AGENT_ENGINEERING, AGENT_PM, make_envelope, submit
from enterprise_router_client import router_configured

message = make_envelope(
    sender=AGENT_PM,
    recipient=AGENT_ENGINEERING,
    task_type="IMPLEMENT_FEATURE",
    message_id="req-002",
    context={
        "priority": "high",
        "target_release": "2026-05-01",
    },
    payload={
        "feature_id": "FT-001",
        "feature_name": "Number guessing game",
        "spec_link": "",
        "acceptance_criteria": [
            "Make an app using Streamlit and Python that simulates a number guessing game",
            "The game generates a random number between 1 and 100",
            "The player has a limited number of attempts to guess the number- after that limit is reached, the player loses",
            "After each guess provide feedback: too high, too low, or correct",
            "The game should have a simple and intuitive user interface",
            "Users should be able to run a main.py file created by the agent to launch the Streamlit app and play the game",
        ],
    },
)


def main() -> None:
    if router_configured():
        prev = os.environ.get("ENTERPRISE_AGENT_NAME")
        os.environ["ENTERPRISE_AGENT_NAME"] = AGENT_PM
        try:
            mid = submit(message)
            print(f"Submitted via enterprise router: message_id={mid}")
        finally:
            if prev is not None:
                os.environ["ENTERPRISE_AGENT_NAME"] = prev
        return

    from pymongo import MongoClient
    from enterprise_paths import inter_agent_mongo_db_name, inter_agent_mongo_uri

    client = MongoClient(inter_agent_mongo_uri())
    db = client[inter_agent_mongo_db_name()]
    result = db.messages.insert_one(message)
    print(f"Inserted legacy Mongo message _id={result.inserted_id}")
    print("Engineering agent will pick this up on its next poll (legacy mode).")


if __name__ == "__main__":
    main()
