"""
CEO-managed distribution tokens: cap how often governed scenarios can result in bus delivery.

- The executive (default name \"CEO\") registers scenarios, mints supply, and assigns balances to agents.
- Each governed send lists a scenario in envelope context (``distribution_scenario`` or ``prompt_scenario``).
- MessageBus (when enforcement is enabled) consumes tokens from the sender's balance before persisting.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from message_schema import EnvelopeInput, envelope_dict


class DistributionTokenError(Exception):
    """Raised when a token-gated send cannot be completed (no persist, no delivery)."""

    def __init__(self, message: str, *, scenario: str, sender: str, balance: int, cost: int):
        super().__init__(message)
        self.scenario = scenario
        self.sender = sender
        self.balance = balance
        self.cost = cost


def resolve_distribution_scenario(envelope: EnvelopeInput) -> Optional[str]:
    """
    Scenario for token accounting. Explicit context wins; otherwise no gating for that message.
    Supported keys: ``distribution_scenario``, ``prompt_scenario``.
    """
    env = envelope_dict(envelope)
    ctx = env.get("context")
    if not isinstance(ctx, dict):
        return None
    for key in ("distribution_scenario", "prompt_scenario"):
        raw = ctx.get(key)
        if isinstance(raw, str):
            s = raw.strip()
            if s:
                return s
    return None


@dataclass
class _ScenarioPolicy:
    cost_per_send: int = 1
    created_by: str = ""


class CeoDistributionTokenRegistry:
    """
    Thread-safe ledger: registered scenarios, per-(holder, scenario) balances.
    Mutating operations require ``acting_executive`` to match ``executive_name``.
    """

    def __init__(self, executive_name: str = "CEO"):
        self.executive_name = executive_name
        self._lock = threading.Lock()
        self._scenarios: Dict[str, _ScenarioPolicy] = {}
        self._balances: Dict[Tuple[str, str], int] = {}

    def _assert_executive(self, acting: str) -> None:
        if acting != self.executive_name:
            raise PermissionError(
                f"Only {self.executive_name!r} may change distribution token policy; got {acting!r}."
            )

    def register_scenario(
        self,
        scenario_id: str,
        *,
        cost_per_send: int = 1,
        acting_executive: str,
    ) -> None:
        sid = (scenario_id or "").strip()
        if not sid:
            raise ValueError("scenario_id must be non-empty")
        if cost_per_send < 1:
            raise ValueError("cost_per_send must be >= 1")
        self._assert_executive(acting_executive)
        with self._lock:
            self._scenarios[sid] = _ScenarioPolicy(
                cost_per_send=cost_per_send,
                created_by=acting_executive,
            )

    def is_registered(self, scenario_id: str) -> bool:
        with self._lock:
            return scenario_id in self._scenarios

    def cost_for(self, scenario_id: str) -> int:
        with self._lock:
            pol = self._scenarios.get(scenario_id)
            return pol.cost_per_send if pol else 1

    def mint(
        self,
        scenario_id: str,
        quantity: int,
        holder: str,
        *,
        acting_executive: str,
    ) -> None:
        if quantity < 0:
            raise ValueError("quantity must be non-negative")
        self._assert_executive(acting_executive)
        sid = (scenario_id or "").strip()
        if not sid:
            raise ValueError("scenario_id must be non-empty")
        h = (holder or "").strip()
        if not h:
            raise ValueError("holder must be non-empty")
        with self._lock:
            if sid not in self._scenarios:
                raise KeyError(f"Unknown scenario {sid!r}; register it first.")
            key = (h, sid)
            self._balances[key] = self._balances.get(key, 0) + quantity

    def transfer(
        self,
        scenario_id: str,
        from_holder: str,
        to_holder: str,
        quantity: int,
        *,
        acting_executive: str,
    ) -> None:
        if quantity < 1:
            raise ValueError("quantity must be >= 1")
        self._assert_executive(acting_executive)
        sid = (scenario_id or "").strip()
        fh = (from_holder or "").strip()
        th = (to_holder or "").strip()
        if not sid or not fh or not th:
            raise ValueError("scenario_id, from_holder, and to_holder are required")
        with self._lock:
            if sid not in self._scenarios:
                raise KeyError(f"Unknown scenario {sid!r}; register it first.")
            fk = (fh, sid)
            tk = (th, sid)
            have = self._balances.get(fk, 0)
            if have < quantity:
                raise ValueError(
                    f"Insufficient tokens: {fh!r} has {have} for {sid!r}, need {quantity}"
                )
            self._balances[fk] = have - quantity
            self._balances[tk] = self._balances.get(tk, 0) + quantity

    def balance(self, holder: str, scenario_id: str) -> int:
        h = (holder or "").strip()
        sid = (scenario_id or "").strip()
        with self._lock:
            return self._balances.get((h, sid), 0)

    def try_consume(self, holder: str, scenario_id: str, cost: Optional[int] = None) -> bool:
        """Atomically decrement balance if enough; return whether send may proceed."""
        h = (holder or "").strip()
        sid = (scenario_id or "").strip()
        with self._lock:
            if sid not in self._scenarios:
                return False
            c = cost if cost is not None else self._scenarios[sid].cost_per_send
            key = (h, sid)
            have = self._balances.get(key, 0)
            if have < c:
                return False
            self._balances[key] = have - c
            return True

    def snapshot_balances(self) -> Dict[Tuple[str, str], int]:
        with self._lock:
            return dict(self._balances)
