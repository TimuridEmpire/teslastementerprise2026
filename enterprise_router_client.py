"""Client adapter for the shared UI-Team enterprise_router API.

Agents in this repo should use this adapter for cross-repo/cloud communication.
The router API owns queueing, auth, SQLite/Mongo persistence, and audit logs.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests  # pyright: ignore[reportMissingModuleSource]

from message_schema import Message


class EnterpriseRouterClient:
    """Small HTTP client for the shared enterprise_router FastAPI service."""

    def __init__(
        self,
        *,
        base_url: str,
        agent_name: str,
        api_key: str,
        timeout_s: float = 10.0,
        session: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_name = agent_name
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.session = session or requests

    @classmethod
    def from_env(
        cls,
        *,
        agent_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> "EnterpriseRouterClient":
        resolved_agent = agent_name or os.getenv("ENTERPRISE_ROUTER_AGENT_NAME", "HR")
        key_env = f"{resolved_agent.upper()}_AGENT_API_KEY"
        resolved_key = (
            api_key
            or os.getenv("ENTERPRISE_ROUTER_AGENT_API_KEY")
            or os.getenv(key_env, "")
        )
        return cls(
            base_url=os.getenv("ENTERPRISE_ROUTER_API_URL", "http://localhost:8000"),
            agent_name=resolved_agent,
            api_key=resolved_key,
            timeout_s=float(os.getenv("ENTERPRISE_ROUTER_TIMEOUT_S", "10")),
        )

    def submit_envelope(
        self,
        envelope: Dict[str, Any],
        *,
        routing_hints: Optional[Dict[str, Any]] = None,
    ) -> str:
        Message.validate_envelope(envelope)
        sender = str(envelope.get("sender", ""))
        if sender != self.agent_name:
            raise ValueError(
                f"Envelope sender {sender!r} does not match authenticated agent "
                f"{self.agent_name!r}."
            )
        data = self._post(
            "/messages",
            {
                "message": envelope,
                "routing_hints": routing_hints or {},
            },
        )
        message_id = data.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            raise ValueError("Router response did not include a message_id.")
        return message_id

    def fetch_next(self, recipient: Optional[str] = None) -> Optional[Dict[str, Any]]:
        target = recipient or self.agent_name
        data = self._post("/messages/fetch-next", {"recipient": target})
        if not data:
            return None
        envelope = data.get("envelope")
        if envelope is None:
            return None
        if not isinstance(envelope, dict):
            raise ValueError("Router fetch response contained a non-object envelope.")
        Message.validate_envelope(envelope)
        return envelope

    def ack_message(self, message_id: str, recipient: Optional[str] = None) -> Dict[str, Any]:
        return self._post(
            f"/messages/{message_id}/ack",
            {"recipient": recipient or self.agent_name},
        )

    def nack_message(
        self,
        message_id: str,
        recipient: Optional[str] = None,
        *,
        reason: str,
    ) -> Dict[str, Any]:
        return self._post(
            f"/messages/{message_id}/nack",
            {"recipient": recipient or self.agent_name, "reason": reason},
        )

    def request_registration(
        self,
        *,
        role: str,
        secret_token: str,
        file_path: str | None = None,
        endpoint: str | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "post",
            "/registrations/request",
            {
                "agent_name": self.agent_name,
                "role": role,
                "secret_token": secret_token,
                "file_path": file_path,
                "endpoint": endpoint,
                "metadata": metadata or {},
            },
            headers={"Content-Type": "application/json"},
        )

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("post", path, body, headers=self._agent_headers())

    def _request(
        self,
        method: str,
        path: str,
        body: Dict[str, Any],
        *,
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        response = getattr(self.session, method)(
            f"{self.base_url}{path}",
            json=body,
            headers=headers,
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object response from {path}.")
        return data

    def _agent_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError(
                "Missing enterprise_router API key. Set ENTERPRISE_ROUTER_AGENT_API_KEY "
                "or <AGENT>_AGENT_API_KEY."
            )
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Agent-Id": self.agent_name,
        }
