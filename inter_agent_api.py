"""
HTTP helpers for inter-agent communication when agents live in separate services.

Persistence:
  * **MongoDB** — envelopes and mailboxes for cross-service traffic (``InterAgentMongoStore``).
  * **SQLite** — in-process internal backlog (``AgentBacklog``); not used by these routes unless you enable mirroring on the store.

Expected server routes:
- POST /messages/send               body: envelope dict
- GET  /messages/receive/{agent}    returns one envelope or null
- GET  /messages/pending/{agent}    returns {"pending": int}

Use ``create_inter_agent_fastapi_app()`` to run the API; requires ``fastapi`` and ``uvicorn``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

import requests #pyright: ignore[reportMissingModuleSource]

if TYPE_CHECKING:
    from inter_agent_mongo import InterAgentMongoStore


def send_envelope_http(
    base_url: str,
    envelope: Dict[str, Any],
    *,
    timeout_s: float = 10.0,
) -> Dict[str, Any]:
    """Send one standardized envelope to a MessageBus HTTP service."""
    url = f"{base_url.rstrip('/')}/messages/send"
    resp = requests.post(url, json=envelope, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object response from /messages/send")
    return data


def receive_envelope_http(
    base_url: str,
    agent_name: str,
    *,
    timeout_s: float = 10.0,
) -> Optional[Dict[str, Any]]:
    """Pull one queued envelope for an agent from an HTTP-backed mailbox."""
    url = f"{base_url.rstrip('/')}/messages/receive/{agent_name}"
    resp = requests.get(url, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json()
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("Expected object-or-null response from /messages/receive/{agent}")
    return data


def pending_count_http(
    base_url: str,
    agent_name: str,
    *,
    timeout_s: float = 10.0,
) -> int:
    """Read queued mailbox depth for an agent from an HTTP service."""
    url = f"{base_url.rstrip('/')}/messages/pending/{agent_name}"
    resp = requests.get(url, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or "pending" not in data:
        raise ValueError("Expected {'pending': <int>} from /messages/pending/{agent}")
    return int(data["pending"])


def create_inter_agent_fastapi_app(store: "InterAgentMongoStore"):
    """
    Build a FastAPI app backed by ``InterAgentMongoStore`` (MongoDB).

    Install: ``pip install fastapi uvicorn pymongo``
    """
    from fastapi import Body, FastAPI, HTTPException

    app = FastAPI(title="Inter-agent messages", version="1.0")

    @app.post("/messages/send")
    def post_send(envelope: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        result = store.record_and_enqueue(envelope)
        if not result.get("ok"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "invalid envelope"),
            )
        return result

    @app.get("/messages/receive/{agent_name}")
    def get_receive(agent_name: str) -> Optional[Dict[str, Any]]:
        return store.pop_next_for_recipient(agent_name)

    @app.get("/messages/pending/{agent_name}")
    def get_pending(agent_name: str) -> Dict[str, int]:
        return {"pending": store.pending_count(agent_name)}

    return app


def run_inter_agent_api_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    mirror_sqlite: bool = False,
) -> None:
    """Convenience: Mongo store from env + uvicorn. For production, use your own ASGI deployment."""
    import uvicorn

    from inter_agent_mongo import inter_agent_store_from_env

    store = inter_agent_store_from_env(mirror_sqlite=mirror_sqlite)
    app = create_inter_agent_fastapi_app(store)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_inter_agent_api_server()
