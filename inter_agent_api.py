"""
HTTP layer for cross-service agent communication via the Enterprise Router.

Run the router API:
  python -m enterprise_router.api

Environment (see ``enterprise_paths`` and ``enterprise_router.config``):
  ENTERPRISE_ROUTER_URL, ENTERPRISE_AGENT_NAME, ENTERPRISE_AGENT_API_KEY — agent clients
  ENTERPRISE_ROUTER_ADMIN_SECRET — admin endpoints
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

import requests  # pyright: ignore[reportMissingModuleSource]

from enterprise_router_client import EnterpriseRouterClient, router_configured
from message_schema import EnvelopeInput, Message, normalize_envelope


def _client_or_raise() -> EnterpriseRouterClient:
    client = EnterpriseRouterClient.from_env()
    if client is None:
        raise RuntimeError(
            "Enterprise router client is not configured. Set ENTERPRISE_ROUTER_URL, "
            "ENTERPRISE_AGENT_NAME, and ENTERPRISE_AGENT_API_KEY."
        )
    return client


def send_envelope_http(
    base_url: str,
    envelope: EnvelopeInput,
    *,
    api_key: str,
    agent_name: str,
    timeout_s: float = 10.0,
    routing_hints: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Submit one envelope through POST /messages (enterprise routing)."""
    env = normalize_envelope(envelope)
    client = EnterpriseRouterClient(base_url, agent_name, api_key, timeout_s=timeout_s)
    message_id = client.submit_message(env, routing_hints=routing_hints)
    return {"ok": True, "message_id": message_id, "id": env.get("id", message_id)}


def receive_envelope_http(
    base_url: str,
    agent_name: str,
    *,
    api_key: str,
    timeout_s: float = 10.0,
) -> Optional[Dict[str, Any]]:
    """Lease the next message via POST /messages/fetch-next."""
    client = EnterpriseRouterClient(base_url, agent_name, api_key, timeout_s=timeout_s)
    return client.fetch_next(agent_name)


def pending_count_http(
    base_url: str,
    agent_name: str,
    *,
    api_key: str,
    timeout_s: float = 10.0,
) -> int:
    """Approximate queue depth via GET /messages/peek."""
    client = EnterpriseRouterClient(base_url, agent_name, api_key, timeout_s=timeout_s)
    return client.pending_count()


def send_envelope(
    envelope: EnvelopeInput,
    *,
    routing_hints: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Send using env-configured enterprise router client."""
    env = normalize_envelope(envelope)
    client = _client_or_raise()
    message_id = client.submit_message(env, routing_hints=routing_hints)
    return {"ok": True, "message_id": message_id, "id": env["id"]}


def receive_envelope(agent_name: str | None = None) -> Optional[Dict[str, Any]]:
    client = _client_or_raise()
    return client.fetch_next(agent_name)


def create_inter_agent_fastapi_app(store: None = None):
    """
    Build the Enterprise Router FastAPI app.

    The ``store`` argument is ignored (kept for backward compatibility).
    """
    from enterprise_router.api import create_app
    from enterprise_router.config import RouterSettings

    return create_app(RouterSettings.from_env())


def run_inter_agent_api_server(
    *,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Start the enterprise router (SQLite-backed) with uvicorn."""
    import uvicorn

    from enterprise_router.config import RouterSettings

    settings = RouterSettings.from_env()
    if host is not None or port is not None:
        settings = RouterSettings(
            sqlite_db_path=settings.sqlite_db_path,
            shared_secret=settings.shared_secret,
            admin_secret=settings.admin_secret,
            api_host=host if host is not None else settings.api_host,
            api_port=port if port is not None else settings.api_port,
        )

    from enterprise_router.api import create_app

    uvicorn.run(create_app(settings), host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    run_inter_agent_api_server()
