"""Client adapter for the shared UI-Team enterprise_router API.

Agents in this repo should use this adapter for cross-repo/cloud communication.
The router API owns queueing, auth, SQLite/Mongo persistence, and audit logs.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests  # pyright: ignore[reportMissingModuleSource]

from message_schema import Message

JsonResponse = Dict[str, Any] | list[Any]


def router_base_url() -> str | None:
    url = (
        os.getenv("ENTERPRISE_ROUTER_API_URL")
        or os.getenv("ENTERPRISE_ROUTER_URL")
        or ""
    ).strip()
    return url.rstrip("/") if url else None


def router_agent_name() -> str | None:
    name = (
        os.getenv("ENTERPRISE_ROUTER_AGENT_NAME")
        or os.getenv("ENTERPRISE_AGENT_NAME")
        or ""
    ).strip()
    return name or None


def router_api_key(agent_name: str | None = None) -> str | None:
    resolved_agent = agent_name or router_agent_name()
    agent_key = ""
    if resolved_agent:
        agent_key = os.getenv(f"{resolved_agent.upper()}_AGENT_API_KEY", "")
    key = (
        os.getenv("ENTERPRISE_ROUTER_AGENT_API_KEY")
        or os.getenv("ENTERPRISE_AGENT_API_KEY")
        or agent_key
        or ""
    ).strip()
    return key or None


def router_configured() -> bool:
    return bool(router_base_url() and router_agent_name() and router_api_key())


def router_missing_config(agent_name: str | None = None) -> list[str]:
    missing: list[str] = []
    resolved_agent = agent_name or router_agent_name()
    if not router_base_url():
        missing.append("ENTERPRISE_ROUTER_API_URL or ENTERPRISE_ROUTER_URL")
    if not resolved_agent:
        missing.append("ENTERPRISE_ROUTER_AGENT_NAME or ENTERPRISE_AGENT_NAME")
    if not router_api_key(resolved_agent):
        missing.append(
            "ENTERPRISE_ROUTER_AGENT_API_KEY, ENTERPRISE_AGENT_API_KEY, "
            "or <AGENT>_AGENT_API_KEY"
        )
    return missing


class EnterpriseRouterClient:
    """Small HTTP client for the shared enterprise_router FastAPI service."""

    def __init__(
        self,
        base_url: str,
        agent_name: str,
        api_key: str,
        *,
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
        resolved_agent = agent_name or router_agent_name()
        resolved_key = api_key or router_api_key(resolved_agent)
        base_url = router_base_url()
        missing = router_missing_config(resolved_agent)
        if resolved_key:
            missing = [item for item in missing if not item.startswith("ENTERPRISE_ROUTER_AGENT_API_KEY")]
        if not missing and resolved_agent and resolved_key and base_url:
            return cls(
                base_url=base_url,
                agent_name=resolved_agent,
                api_key=resolved_key,
                timeout_s=float(os.getenv("ENTERPRISE_ROUTER_TIMEOUT_S", "10")),
            )
        raise RuntimeError(
            "Missing Enterprise Router configuration: "
            + ", ".join(missing)
            + ". Runtime agent communication must use the Enterprise Router; "
            "set ENTERPRISE_ROUTER_OFFLINE_DEMO=1 only for local demos/tests."
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

    def submit_message(
        self,
        envelope: Dict[str, Any] | Message,
        *,
        routing_hints: Optional[Dict[str, Any]] = None,
    ) -> str:
        body = envelope.to_dict() if isinstance(envelope, Message) else dict(envelope)
        return self.submit_envelope(body, routing_hints=routing_hints)

    def fetch_next(self, recipient: Optional[str] = None) -> Optional[Dict[str, Any]]:
        item = self.fetch_next_item(recipient)
        if not item:
            return None
        envelope = item.get("envelope") or item.get("message")
        if envelope is None and item.get("id"):
            envelope = item
        if envelope is None:
            return None
        if not isinstance(envelope, dict):
            raise ValueError("Router fetch response contained a non-object envelope.")
        Message.validate_envelope(envelope)
        return envelope

    def fetch_next_item(self, recipient: Optional[str] = None) -> Optional[Dict[str, Any]]:
        target = recipient or self.agent_name
        data = self._post("/messages/fetch-next", {"recipient": target})
        if not data:
            return None
        return self._require_object(data, "/messages/fetch-next")

    def peek(self, limit: int = 10) -> list[Dict[str, Any]]:
        rows = self.peek_items(limit=limit)
        envelopes: list[Dict[str, Any]] = []
        for item in rows:
            envelope = item.get("envelope") or item.get("message")
            if isinstance(envelope, dict):
                Message.validate_envelope(envelope)
                envelopes.append(envelope)
        return envelopes

    def peek_items(self, limit: int = 10) -> list[Dict[str, Any]]:
        data = self._request(
            "get",
            "/messages/peek",
            {"recipient": self.agent_name, "limit": limit},
            headers=self._agent_headers(),
        )
        if not isinstance(data, list):
            return []
        items: list[Dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            items.append(item)
        return items

    def ack_message(self, message_id: str, recipient: Optional[str] = None) -> Dict[str, Any]:
        return self._post(
            f"/messages/{message_id}/ack",
            {"recipient": recipient or self.agent_name},
        )

    def ack(self, message_id: str, recipient: Optional[str] = None) -> None:
        self.ack_message(message_id, recipient)

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

    def nack(self, message_id: str, reason: str, recipient: Optional[str] = None) -> None:
        self.nack_message(message_id, recipient, reason=reason)

    def pending_count(self) -> int:
        return len(self.peek(limit=500))

    def request_registration(
        self,
        *,
        role: str,
        secret_token: str,
        file_path: str | None = None,
        endpoint: str | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = self._request(
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
        return self._require_object(data, "/registrations/request")

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        data = self._request("post", path, body, headers=self._agent_headers())
        return self._require_object(data, path)

    def _request(
        self,
        method: str,
        path: str,
        body: Dict[str, Any],
        *,
        headers: Dict[str, str],
    ) -> JsonResponse:
        if method.lower() == "get":
            response = self.session.get(
                f"{self.base_url}{path}",
                params=body,
                headers=headers,
                timeout=self.timeout_s,
            )
        else:
            response = getattr(self.session, method)(
                f"{self.base_url}{path}",
                json=body,
                headers=headers,
                timeout=self.timeout_s,
            )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, (dict, list)):
            raise ValueError(f"Expected JSON object or list response from {path}.")
        return data

    def _require_object(self, data: JsonResponse, path: str) -> Dict[str, Any]:
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
