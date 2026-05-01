from __future__ import annotations

import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from langchain.tools import tool  # pyright: ignore[reportMissingImports]
except ImportError:  # pragma: no cover - lets tests run without LangChain installed
    def tool(func):
        return func


_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent_backlog import AgentBacklog
from enterprise_router_client import EnterpriseRouterClient


HR_AGENT_NAME = os.getenv("HR_AGENT_NAME", "HR")
agentBacklog = AgentBacklog()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def router_client_from_env(agent_name: str = HR_AGENT_NAME) -> EnterpriseRouterClient:
    return EnterpriseRouterClient.from_env(agent_name=agent_name)


def build_envelope(
    *,
    sender: str,
    recipient: str,
    task_type: str,
    context: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    prefix: str = "msg",
) -> Dict[str, Any]:
    return {
        "id": f"{prefix}-{uuid.uuid4().hex[:8]}",
        "timestamp": utc_timestamp(),
        "sender": sender,
        "recipient": recipient,
        "task_type": task_type,
        "context": context or {},
        "payload": payload or {},
        "status": "pending",
        "error": "",
    }


def queue_mint_token_request(
    scenario_id: str,
    quantity: int,
    holder: str = HR_AGENT_NAME,
    *,
    router_client: Optional[EnterpriseRouterClient] = None,
) -> str:
    client = router_client or router_client_from_env(HR_AGENT_NAME)
    envelope = build_envelope(
        sender=HR_AGENT_NAME,
        recipient="CEO",
        task_type="MINT_TOKENS",
        payload={
            "scenario_id": scenario_id,
            "quantity": quantity,
            "holder": holder,
        },
        prefix="mint",
    )
    message_id = client.submit_envelope(
        envelope,
        routing_hints={
            "urgency": "normal",
            "provenance_source": "hr_agent",
            "provenance_agent": HR_AGENT_NAME,
        },
    )
    return f"Mint request queued: {message_id}"


@tool
def request_mint_tokens(scenario_id: str, quantity: int, holder: str = HR_AGENT_NAME) -> str:
    """
    Ask the CEO agent to mint distribution tokens for a scenario and holder.
    """
    return queue_mint_token_request(scenario_id, quantity, holder)


def callSupervisor(query: Dict[str, Any]) -> None:
    """
    Process one HR message. The expensive LLM imports stay inside this function
    so router polling and tests do not require Ollama/LangChain at import time.
    """
    agentBacklog.update_status(query["id"], "in_progress")
    try:
        from langchain.agents import create_agent  # pyright: ignore[reportMissingImports]
        from langchain_ollama import ChatOllama  # pyright: ignore[reportMissingImports]

        hr_agent = create_agent(
            model=ChatOllama(model="mistral").bind_tools([request_mint_tokens]),
            tools=[request_mint_tokens],
            system_prompt=(
                "You are an HR agent. Use the provided tools to request token "
                "minting from the CEO."
            ),
        )
        hr_agent.invoke(query)
    except Exception as exc:
        agentBacklog.update_status(query["id"], "error", str(exc))
        raise
    else:
        agentBacklog.update_status(query["id"], "done")


def process_one_hr_message(
    *,
    router_client: Optional[EnterpriseRouterClient] = None,
    supervisor: Callable[[Dict[str, Any]], Any] = callSupervisor,
    backlog: AgentBacklog = agentBacklog,
    recipient: str = HR_AGENT_NAME,
) -> bool:
    """
    Fetch one HR message from the shared enterprise_router queue and process it.
    Returns True when a message was found, False when the queue was empty.
    """
    client = router_client or router_client_from_env(recipient)
    envelope = client.fetch_next(recipient)
    if envelope is None:
        return False

    message_id = envelope.get("id", "")
    backlog.record_interaction(envelope)
    try:
        supervisor(envelope)
    except Exception as exc:
        client.nack_message(message_id, recipient, reason=str(exc))
        return True

    client.ack_message(message_id, recipient)
    return True


def seed_sample_message(router_client: Optional[EnterpriseRouterClient] = None) -> str:
    """Queue a sample CEO -> HR message through enterprise_router for demos."""
    client = router_client or EnterpriseRouterClient.from_env(agent_name="CEO")
    envelope = build_envelope(
        sender="CEO",
        recipient=HR_AGENT_NAME,
        task_type="TALENT_REALLOCATION",
        context={"quarter": "Q2", "year": 2026},
        payload={"task": "Hire 10 engineering agents, and fire all 20 marketing agents"},
        prefix="req",
    )
    return client.submit_envelope(envelope)


def hr_worker(
    worker_id: int,
    stop_event: threading.Event,
    *,
    router_client: Optional[EnterpriseRouterClient] = None,
) -> None:
    """Poll enterprise_router for HR messages and process them."""
    name = f"HR-Worker-{worker_id}"
    client = router_client or router_client_from_env(HR_AGENT_NAME)
    while not stop_event.is_set():
        try:
            processed = process_one_hr_message(router_client=client)
            if not processed:
                time.sleep(0.5)
                continue
            print(f"{name} processed one HR message")
        except Exception as exc:
            print(f"{name} failed while polling enterprise_router: {exc}")
            time.sleep(1.0)


def main(num_workers: int = 3) -> None:
    stop_event = threading.Event()
    threads = []
    for i in range(num_workers):
        t = threading.Thread(target=hr_worker, args=(i + 1, stop_event), daemon=True)
        t.start()
        threads.append(t)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down HR workers...")
        stop_event.set()
        for t in threads:
            t.join(timeout=1)


if __name__ == "__main__":
    main(num_workers=4)
