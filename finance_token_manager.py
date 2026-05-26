"""
finance_token_manager.py

Finance-managed distribution token system.

Responsibilities:
  - Finance (CFO) creates and distributes tokens to all agents
  - When any agent's tokens are maxed out, they send a TOKEN_TOPUP_REQUEST to Finance
  - Finance evaluates and approves/denies
  - CEO is notified (FYI) — approval authority is Finance/CFO, not CEO
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ── Repo imports ──────────────────────────────────────────────────────────────
from ceo_distribution_tokens import CeoDistributionTokenRegistry   # repo root
from message_schema import Message                                  # repo root

logger = logging.getLogger("finance_token_manager")

# ── Default starting allocations (Finance sets these) ────────────────────────

DEFAULT_ALLOCATIONS: Dict[str, int] = {
    "CEO":         30,
    "PM":          25,
    "Engineering": 20,
    "Marketing":   15,
    "HR":          10,
    "Sales":       10,
    "Finance":     10,
    "UI":          10,
}

DEFAULT_TOPUP_AMOUNT = 10

STANDARD_SCENARIO  = "STANDARD_DELEGATION"
BROADCAST_SCENARIO = "EXECUTIVE_BROADCAST"


# ── Token request record ──────────────────────────────────────────────────────

@dataclass
class TokenRequest:
    agent_name: str
    scenario_id: str
    requested_amount: int
    reason: str
    requested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "pending"          # pending | approved | denied
    approved_amount: int = 0
    decided_at: Optional[str] = None
    ceo_notified: bool = False


# ── Finance Token Manager ─────────────────────────────────────────────────────

class FinanceTokenManager:
    """
    Finance (CFO) owns token issuance and top-up approvals.

    Wraps CeoDistributionTokenRegistry but uses Finance as the acting executive
    so Finance — not CEO — is the minting authority.

    Usage:
        manager = FinanceTokenManager(router_client=client)
        manager.initialize_registry()        # mint + distribute starting tokens
        manager.handle_topup_request(...)    # called when an agent runs out
    """

    def __init__(
        self,
        router_client=None,
        executive_name: str = "CEO",
        cfo_name: str = "Finance",
    ):
        self.router_client  = router_client
        self.executive_name = executive_name   # CEO receives FYI notifications
        self.cfo_name       = cfo_name         # Finance is the acting authority

        # Finance acts as the minting executive for the registry
        self.registry = CeoDistributionTokenRegistry(executive_name=cfo_name)

        self._lock: threading.Lock = threading.Lock()
        self._requests: List[TokenRequest] = []

    # ── Setup ─────────────────────────────────────────────────────────────────

    def initialize_registry(self) -> None:
        """
        Register scenarios and distribute starting token balances.
        Called once at Finance agent startup.
        """
        # Register scenarios
        self.registry.register_scenario(
            STANDARD_SCENARIO,
            cost_per_send=1,
            acting_executive=self.cfo_name,
        )
        self.registry.register_scenario(
            BROADCAST_SCENARIO,
            cost_per_send=3,
            acting_executive=self.cfo_name,
        )

        # Mint total standard supply into Finance's account
        total_standard = sum(DEFAULT_ALLOCATIONS.values())
        self.registry.mint(
            STANDARD_SCENARIO,
            quantity=total_standard,
            holder=self.cfo_name,
            acting_executive=self.cfo_name,
        )

        # Mint broadcast supply
        self.registry.mint(
            BROADCAST_SCENARIO,
            quantity=15,
            holder=self.cfo_name,
            acting_executive=self.cfo_name,
        )

        # Distribute standard tokens to each agent
        for agent, amount in DEFAULT_ALLOCATIONS.items():
            if agent == self.cfo_name:
                continue  # Finance already holds its own share
            self.registry.transfer(
                STANDARD_SCENARIO,
                from_holder=self.cfo_name,
                to_holder=agent,
                quantity=amount,
                acting_executive=self.cfo_name,
            )

        # Distribute broadcast tokens (CEO + PM only per README spec)
        self.registry.transfer(
            BROADCAST_SCENARIO,
            from_holder=self.cfo_name,
            to_holder=self.executive_name,
            quantity=12,
            acting_executive=self.cfo_name,
        )
        self.registry.transfer(
            BROADCAST_SCENARIO,
            from_holder=self.cfo_name,
            to_holder="PM",
            quantity=3,
            acting_executive=self.cfo_name,
        )

        logger.info(
            "[FinanceTokenManager] Registry initialized — %d standard tokens "
            "distributed across %d agents.",
            total_standard, len(DEFAULT_ALLOCATIONS),
        )
        self._log_balances()

    # ── Token request handling ────────────────────────────────────────────────

    def handle_topup_request(
        self,
        agent_name: str,
        scenario_id: str,
        requested_amount: int,
        reason: str = "",
    ) -> Dict[str, Any]:
        """
        Called when an agent's tokens are maxed out.

        Flow:
          1. Finance (CFO) evaluates and approves/denies
          2. If approved, mint new tokens and transfer to the agent
          3. Notify CEO (FYI only — approval comes from Finance/CFO)
        """
        req = TokenRequest(
            agent_name=agent_name,
            scenario_id=scenario_id,
            requested_amount=requested_amount,
            reason=reason or f"{agent_name} token balance exhausted for {scenario_id}",
        )
        with self._lock:
            self._requests.append(req)

        logger.info(
            "[FinanceTokenManager] Top-up request from %s: %d tokens for %s",
            agent_name, requested_amount, scenario_id,
        )

        approved, approved_amount, denial_reason = self._cfo_evaluate(req)

        req.status          = "approved" if approved else "denied"
        req.approved_amount = approved_amount
        req.decided_at      = datetime.now(timezone.utc).isoformat()

        if approved:
            self._mint_and_transfer(agent_name, scenario_id, approved_amount)
            logger.info(
                "[FinanceTokenManager] CFO approved %d tokens for %s (%s).",
                approved_amount, agent_name, scenario_id,
            )
        else:
            logger.warning(
                "[FinanceTokenManager] CFO denied top-up for %s: %s",
                agent_name, denial_reason,
            )

        # Notify CEO — FYI only, no approval needed from CEO
        self._notify_ceo(req, denial_reason)

        return {
            "status":           req.status,
            "agent":            agent_name,
            "scenario_id":      scenario_id,
            "requested_amount": requested_amount,
            "approved_amount":  approved_amount,
            "decided_at":       req.decided_at,
            "denial_reason":    denial_reason if not approved else None,
            "ceo_notified":     req.ceo_notified,
        }

    def _cfo_evaluate(self, req: TokenRequest) -> Tuple[bool, int, str]:
        """CFO decision logic. Returns (approved, approved_amount, denial_reason)."""
        if not self.registry.is_registered(req.scenario_id):
            return False, 0, f"Unknown scenario: {req.scenario_id}"

        approved_amount = min(req.requested_amount, DEFAULT_TOPUP_AMOUNT)

        # Ensure Finance has enough supply; mint more if needed
        finance_balance = self.registry.balance(self.cfo_name, req.scenario_id)
        if finance_balance < approved_amount:
            shortfall = approved_amount - finance_balance
            self.registry.mint(
                req.scenario_id,
                quantity=shortfall + DEFAULT_TOPUP_AMOUNT,
                holder=self.cfo_name,
                acting_executive=self.cfo_name,
            )
            logger.info(
                "[FinanceTokenManager] CFO minted %d additional tokens for supply.",
                shortfall + DEFAULT_TOPUP_AMOUNT,
            )

        return True, approved_amount, ""

    def _mint_and_transfer(self, agent_name: str, scenario_id: str, amount: int) -> None:
        self.registry.transfer(
            scenario_id,
            from_holder=self.cfo_name,
            to_holder=agent_name,
            quantity=amount,
            acting_executive=self.cfo_name,
        )

    def _notify_ceo(self, req: TokenRequest, denial_reason: str = "") -> None:
        """Send FYI message to CEO about the token top-up decision."""
        if not self.router_client:
            logger.debug("[FinanceTokenManager] No router client; CEO notification skipped.")
            return

        msg = Message.create(
            sender=self.cfo_name,
            recipient=self.executive_name,
            task_type="TOKEN_TOPUP_NOTIFICATION",
            payload={
                "event":            "TOKEN_TOPUP_DECISION",
                "agent":            req.agent_name,
                "scenario_id":      req.scenario_id,
                "requested_amount": req.requested_amount,
                "approved_amount":  req.approved_amount,
                "status":           req.status,
                "decided_by":       f"{self.cfo_name} (CFO)",
                "note":             "FYI only — approval authority is Finance/CFO, not CEO.",
                "denial_reason":    denial_reason or None,
                "decided_at":       req.decided_at,
            },
            context={"fyi": True},
        )

        try:
            self.router_client.submit_message(msg)
            req.ceo_notified = True
            logger.info(
                "[FinanceTokenManager] CEO notified (FYI) of token decision for %s.",
                req.agent_name,
            )
        except Exception as exc:
            logger.warning("[FinanceTokenManager] Failed to notify CEO: %s", exc)

    # ── Convenience helpers ───────────────────────────────────────────────────

    def get_balance(self, agent_name: str, scenario_id: str = STANDARD_SCENARIO) -> int:
        return self.registry.balance(agent_name, scenario_id)

    def try_consume(self, agent_name: str, scenario_id: str) -> bool:
        """
        Consume a token. If the balance is empty, automatically request a
        top-up from Finance before retrying.
        """
        if self.registry.try_consume(agent_name, scenario_id):
            return True

        logger.warning(
            "[FinanceTokenManager] %s is out of tokens for %s — requesting top-up.",
            agent_name, scenario_id,
        )
        result = self.handle_topup_request(
            agent_name=agent_name,
            scenario_id=scenario_id,
            requested_amount=DEFAULT_TOPUP_AMOUNT,
            reason=f"{agent_name} token balance exhausted for {scenario_id}",
        )
        if result["status"] == "approved" and result["approved_amount"] > 0:
            return self.registry.try_consume(agent_name, scenario_id)
        return False

    def snapshot(self) -> Dict[str, Any]:
        balances = self.registry.snapshot_balances()
        return {
            "balances": {
                f"{holder}::{scenario}": amount
                for (holder, scenario), amount in balances.items()
            },
            "topup_requests": [
                {
                    "agent":            r.agent_name,
                    "scenario_id":      r.scenario_id,
                    "requested_amount": r.requested_amount,
                    "approved_amount":  r.approved_amount,
                    "status":           r.status,
                    "requested_at":     r.requested_at,
                    "decided_at":       r.decided_at,
                    "ceo_notified":     r.ceo_notified,
                }
                for r in self._requests
            ],
        }

    def _log_balances(self) -> None:
        for (holder, scenario), amount in self.registry.snapshot_balances().items():
            logger.debug("  Balance  %-20s %-30s = %d", holder, scenario, amount)
