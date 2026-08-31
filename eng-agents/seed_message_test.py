"""
Insert a test PM -> Engineering message via the enterprise router (or the
local in-process MessageBus when ENTERPRISE_ROUTER_OFFLINE_DEMO=1).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent_transport import (
    AGENT_ENGINEERING,
    AGENT_PM,
    make_envelope,
    submit,
)

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
            "The player has a limited number of attempts to guess the number; after that limit is reached, the player loses",
            "After each guess provide feedback: too high, too low, or correct",
            "The game should have a simple and intuitive user interface",
            "Users should be able to run a main.py file created by the agent to launch the Streamlit app and play the game",
        ],
    },
)


def main() -> None:
    mid = submit(message)
    print(f"Submitted via enterprise router (or local bus): message_id={mid}")


if __name__ == "__main__":
    main()
