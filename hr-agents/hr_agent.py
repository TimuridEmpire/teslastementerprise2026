import sys
import threading
import time
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

from langchain.tools import tool  # pyright: ignore[reportMissingImports]
from langchain.agents import create_agent  # pyright: ignore[reportMissingImports]
from langchain_ollama import ChatOllama  # pyright: ignore[reportMissingImports]
from langgraph.pregel.main import Output  # pyright: ignore[reportMissingImports]

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent_backlog import AgentBacklog
from agent_transport import AGENT_CEO, AGENT_HR, ack, make_envelope, receive, submit
from message_schema import Message

agentBacklog = AgentBacklog()

# --- Prompts ---
SUPERVISOR_PROMPT = (
    "You are an HR Supervisor agent. "
    "You receive tasks and must delegate them using your specialized sub-agents. "
    "Use callParserAgent to understand complex JSON or file instructions. "
    "Use callEmployeeManagementAgent to actually hire or fire personnel. "
    "Use request_mint_tokens if you need to ask the CEO to mint tokens. "
    "Do not perform tasks not specified in your instructions."
)

PARSER_PROMPT = (
    "You are a parser agent. Extract data from necessary files (primarily JSON). "
    "Compile the data into one clear plan of action regarding hiring or firing agents. "
    "Only include tasks explicitly found in the files."
)

EMPLOYEE_MANAGEMENT_PROMPT = (
    "You are an HR employee management agent. "
    "You receive instructions from the supervisor to hire or fire agents. "
    "Use your hireAgents and fireAgents tools to complete these tasks. "
    "Output the result of your actions."
)


@tool
def request_mint_tokens(scenario_id: str, quantity: int, holder: str = "HR") -> str:
    """Tool: ask the CEO agent to mint distribution tokens for a given scenario."""
    envelope = make_envelope(
        sender=AGENT_HR,
        recipient=AGENT_CEO,
        task_type="MINT_TOKENS",
        payload={"scenario_id": scenario_id, "quantity": quantity, "holder": holder},
    )
    mid = submit(envelope)
    return f"Mint request queued: message_id={mid}"


@tool
def parseJson(path: str):
    """Take in the path to a json file as input and output the parsed json file."""
    with open(path, "r") as file:
        data = json.load(file)
    return data


@tool
def fireAgents(number: int, agent_type: str):
    """Fire the specified number and type of agents."""
    agentBacklog.record_log("current-req", AGENT_HR, "fired", {"number": number, "type": agent_type})
    return f"{number} {agent_type} agents fired."


@tool
def hireAgents(number: int, agent_type: str):
    """Hire the specified number and type of agents."""
    agentBacklog.record_log("current-req", AGENT_HR, "hired", {"number": number, "type": agent_type})
    return f"{number} {agent_type} agents hired."


parserAgent = create_agent(
    model=ChatOllama(model="mistral").bind_tools([parseJson]),
    tools=[parseJson],
    system_prompt=PARSER_PROMPT,
)

employeeManagementAgent = create_agent(
    model=ChatOllama(model="mistral").bind_tools([hireAgents, fireAgents]),
    tools=[hireAgents, fireAgents],
    system_prompt=EMPLOYEE_MANAGEMENT_PROMPT,
)


@tool
def callParserAgent(query: str):
    """Invokes the parser agent with a given query to read files."""
    result = parserAgent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content


@tool
def callEmployeeManagementAgent(query: str):
    """Invokes the employee management agent to execute hire/fire commands."""
    result = employeeManagementAgent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content


def callSupervisor(envelope):
    """Main entry point for processing a message envelope."""
    req_id = envelope.get("id", "unknown-id")
    agentBacklog.update_status(req_id, "in_progress")

    supervisor_tools = [callEmployeeManagementAgent, callParserAgent, request_mint_tokens]
    supervisor_agent = create_agent(
        model=ChatOllama(model="mistral").bind_tools(supervisor_tools),
        tools=supervisor_tools,
        system_prompt=SUPERVISOR_PROMPT,
    )

    try:
        query_content = json.dumps(envelope.get("payload", {}))
        supervisor_agent.invoke({"messages": [{"role": "user", "content": query_content}]})
    except Exception as e:
        print(f"Agent execution failed: {e}")
        agentBacklog.update_status(req_id, "failed")
        return

    agentBacklog.update_status(req_id, "done")


def hr_worker(worker_id: int, stop_event: threading.Event):
    """Poll the enterprise router (or local bus) for HR messages."""
    name = f"HR-Worker-{worker_id}"
    while not stop_event.is_set():
        envelope = receive(AGENT_HR)
        if envelope is None:
            time.sleep(0.5)
            continue
        try:
            print(f"{name} processing message {envelope.get('id')}")
            callSupervisor(envelope)
            mid = envelope.get("id")
            if mid:
                ack(str(mid), AGENT_HR)
            print(f"{name} finished message {envelope.get('id')}")
        except Exception as exc:
            print(f"{name} failed to process {envelope.get('id')}: {exc}")


def main(num_workers: int = 3):
    sample = make_envelope(
        sender=AGENT_CEO,
        recipient=AGENT_HR,
        task_type="TALENT_REALLOCATION",
        payload={
            "task": "Hire 10 engineering agents, and fire all 20 marketing agents"
        },
    )
    mid = submit(sample)
    print(f"Sample message enqueued: {mid}")

    stop_event = threading.Event()
    threads = []
    for i in range(num_workers):
        t = threading.Thread(target=hr_worker, args=(i + 1, stop_event), daemon=True)
        t.start()
        threads.append(t)

    try:
        print("Workers running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down HR workers safely...")
        stop_event.set()
        for t in threads:
            t.join(timeout=1)


if __name__ == "__main__":
    main(num_workers=3)
