"""
HTTP client for the Enterprise Router API.

Agents set:
  ENTERPRISE_ROUTER_URL   — e.g. http://127.0.0.1:8765
  ENTERPRISE_AGENT_NAME   — registered agent id (X-Agent-Id header)
  ENTERPRISE_AGENT_API_KEY — bearer token from admin registration
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests  # pyright: ignore[reportMissingModuleSource]

from message_schema import EnvelopeInput, Message, normalize_envelope


def router_base_url() -> str | None:
    url = (os.getenv("ENTERPRISE_ROUTER_URL") or "").strip()
    return url.rstrip("/") if url else None


def router_agent_name() -> str | None:
    name = (os.getenv("ENTERPRISE_AGENT_NAME") or "").strip()
    return name or None


def router_api_key() -> str | None:
    key = (os.getenv("ENTERPRISE_AGENT_API_KEY") or "").strip()
    return key or None


def router_configured() -> bool:
    return bool(router_base_url() and router_agent_name() and router_api_key())


class EnterpriseRouterClient:
    def __init__(
        self,
        base_url: str,
        agent_name: str,
        api_key: str,
        *,
        timeout_s: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_name = agent_name.strip()
        self.api_key = api_key.strip()
        self.timeout_s = timeout_s

    @classmethod
    def from_env(cls) -> EnterpriseRouterClient | None:
        base = router_base_url()
        name = router_agent_name()
        key = router_api_key()
        if not (base and name and key):
            return None
        return cls(base, name, key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Agent-Id": self.agent_name,
            "Content-Type": "application/json",
        }

    def submit_message(
        self,
        envelope: EnvelopeInput,
        *,
        routing_hints: dict[str, Any] | None = None,
    ) -> str:
        body_msg = normalize_envelope(envelope)
        if body_msg.get("sender") != self.agent_name:
            raise ValueError(
                f"Envelope sender {body_msg.get('sender')!r} must match client agent {self.agent_name!r}."
            )
        resp = requests.post(
            f"{self.base_url}/messages",
            json={"message": body_msg, "routing_hints": routing_hints or {}},
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("message_id") or body_msg.get("id") or "")

    def fetch_next(self, recipient: str | None = None) -> Optional[Dict[str, Any]]:
        who = (recipient or self.agent_name).strip()
        resp = requests.post(
            f"{self.base_url}/messages/fetch-next",
            json={"recipient": who},
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        msg = data.get("message")
        if isinstance(msg, dict) and msg.get("id"):
            return msg
        if data.get("id"):
            return data
        return None

    def peek(self, limit: int = 10) -> list[dict[str, Any]]:
        resp = requests.get(
            f"{self.base_url}/messages/peek",
            params={"recipient": self.agent_name, "limit": limit},
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not isinstance(rows, list):
            return []
        out: list[dict[str, Any]] = []
        for row in rows:
            msg = row.get("message") if isinstance(row, dict) else None
            if isinstance(msg, dict):
                out.append(msg)
        return out

    def ack(self, message_id: str, recipient: str | None = None) -> None:
        who = (recipient or self.agent_name).strip()
        resp = requests.post(
            f"{self.base_url}/messages/{message_id}/ack",
            json={"recipient": who},
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()

    def nack(self, message_id: str, reason: str, recipient: str | None = None) -> None:
        who = (recipient or self.agent_name).strip()
        resp = requests.post(
            f"{self.base_url}/messages/{message_id}/nack",
            json={"recipient": who, "reason": reason},
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()

    def pending_count(self) -> int:
        return len(self.peek(limit=500))
