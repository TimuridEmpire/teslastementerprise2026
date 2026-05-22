import sys
import threading
import time
from pathlib import Path

from langchain.tools import tool  # pyright: ignore[reportMissingImports]
from langchain.agents import create_agent  # pyright: ignore[reportMissingImports]
from langchain_ollama import ChatOllama  # pyright: ignore[reportMissingImports]
import json

# Repo-root agent_backlog (same SQLite as MessageBus / other agents)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from agent_backlog import AgentBacklog

agentBacklog = AgentBacklog()
from langgraph.pregel.main import Output  # pyright: ignore[reportMissingImports]

# Use the shared Mongo-backed inter-agent store (same DB used by CEO)
from inter_agent_mongo import inter_agent_store_from_env
from datetime import datetime, timezone
import uuid
from message_bus import MessageBus

inter_store = inter_agent_store_from_env(mirror_sqlite=False)
message_bus = MessageBus(backlog=agentBacklog)


@tool
def setAgentTheadcount(counts: dict = None, default: int = 2):
    """
    Announce per-agent thread allocation to all agents by writing THREAD_ALLOCATION
    envelopes into the shared Mongo inter-agent store. The database used is the
    same one returned by inter_agent_store_from_env().

    counts: optional mapping {agent_name: thread_count}. If omitted, a sensible
            default set of departments will be informed with the provided default.
    Returns a dict of agent -> record_and_enqueue result.
    """
    agents = [
        "PM Agent",
        "Engineering Agent",
        "Marketing Agent",
        "Sales Agent",
        "Finance Agent",
        "Legal Compliance Agent",
        "Advisor",
        "CEO",
    ]
    if counts is None:
        counts = {a: default for a in agents}

    results = {}
    for agent_name, thread_count in counts.items():
        # don't send allocation to HR itself
        if (agent_name or "").strip().lower() == "hr":
            continue
        envelope = {
            "id": f"thr-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sender": "HR",
            "recipient": agent_name,
            "task_type": "THREAD_ALLOCATION",
            "context": {},
            "payload": {"max_threads": int(thread_count)},
            "status": "pending",
            "error": "",
        }
        try:
            res = inter_store.record_and_enqueue(envelope)
        except Exception as exc:
            res = {"ok": False, "error": str(exc)}
        results[agent_name] = res
    return results

@tool
def request_mint_tokens(scenario_id: str, quantity: int, holder: str = "HR") -> str:
    """
    Tool: ask the CEO agent to mint distribution tokens for a given scenario and holder.
    """
    # Build an envelope addressed to the CEO so the CEO agent can handle the mint request.
    envelope = {
        "id": f"mint-{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sender": "HR",
        "recipient": "CEO",
        "task_type": "MINT_TOKENS",
        "context": {},
        "payload": {"scenario_id": scenario_id, "quantity": quantity, "holder": holder},
        "status": "pending",
        "error": "",
    }
    result = inter_store.record_and_enqueue(envelope)
    return f"Mint request queued: {result}"


def callSupervisor(query):
    """
    Minimal supervisor handler: mark task in progress and done around processing.
    Actual task processing is handled by hr worker threads that poll the message bus.
    """
    agentBacklog.update_status(query["id"], "in_progress")
    # Create an HR agent (Ollama / "mistral") with the request_mint_tokens tool bound
    hr_agent = create_agent(
        model=ChatOllama(model="mistral").bind_tools([request_mint_tokens]),
        tools=[request_mint_tokens],
        system_prompt=("You are an HR agent. Use the provided tools to request token minting from the CEO."),
    )
    try:
        # Invoke the agent with the incoming query envelope
        hr_agent.invoke(query)
    except:
        agentBacklog.update_status(query["id"], "failed")
        return;
    finally:
        agentBacklog.update_status(query["id"], "done")

sample_message = {
    "id": "req-001",
    "timestamp": "2026-03-01T10:00:00Z",
    "sender": "CEO",
    "recipient": "HR",
    "task_type": "TALENT_REALLOCATION",
    "context": {
        "quarter": "Q2",
        "year": 2026
    },
    "payload": {
        "task": "Hire 10 engineering agents, and fire all 20 marketing agents"
    },
    "status": "pending",
    "error": ""
}
# Insert the sample message into the shared Mongo inbox so HR workers can pick it up
inter_store.record_and_enqueue(sample_message)


def hr_worker(worker_id: int, stop_event: threading.Event):
    """Poll the message bus for HR messages and process them."""
    name = f"HR-Worker-{worker_id}"
    while not stop_event.is_set():
        envelope = message_bus.receive("HR")
        if envelope is None:
            # no messages, sleep briefly
            time.sleep(0.5)
            continue
        try:
            print(f"{name} picked up message {envelope.get('id')}")
            callSupervisor(envelope)
            print(f"{name} finished message {envelope.get('id')}")
        except Exception as exc:
            print(f"{name} failed to process {envelope.get('id')}: {exc}")


def main(num_workers: int = 3):
    stop_event = threading.Event()
    threads = []
    for i in range(num_workers):
        t = threading.Thread(target=hr_worker, args=(i + 1, stop_event), daemon=True)
        t.start()
        threads.append(t)
    try:
        # keep main thread alive while workers run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down HR workers...")
        stop_event.set()
        for t in threads:
            t.join(timeout=1)


if __name__ == "__main__":
    main(num_workers=4)
