# Kanosei Agent Workflow Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all implemented Kanosei agents communicate through the Enterprise Router, emit website-visible artifacts, and use clear token ownership boundaries.

**Architecture:** Keep the Enterprise Router as the runtime boundary. Reuse existing agent modules and add the smallest compatibility shims needed for Finance and Sales to run through `run_agents.py`. Treat Finance as owner of routine delegation/cost tokens and CEO as owner of strategic authority/policy tokens only.

**Tech Stack:** Python agents, FastAPI enterprise_router, SQLite local backend, markdown artifacts, pytest regression tests.

---

## Files

- Modify: `agent_logic_structures/Enterprise_Router_Implementation_Guide.md` to document artifact and token ownership contracts.
- Modify: `scripts/bootstrap_router_agents.py` to permit Sales/Finance/token task types.
- Modify: `run_agents.py` and `run_single_agent.py` to launch Sales and Finance when keys exist.
- Modify: `finance-agents/finance_agent.py` to use correct router client APIs and write artifacts.
- Modify: `sales-agents/sales_agent.py` to fix imports, router polling, outbound router messages, and artifacts.
- Modify: `marketing-agents/marketing_agent.py` and `ceo-agents/advisor_agent.py` if artifact gaps remain.
- Create/modify tests under `tests/` for allowlists, launchability, token ownership, and artifact creation.

## Tasks

### Task 1: Contract and allowlists
- [ ] Document token ownership: router API keys are router-owned; routine delegation/top-up and LLM cost tokens are Finance-owned; executive policy/scenario authority remains CEO-owned only when explicitly strategic.
- [ ] Document per-agent artifact expectations.
- [ ] Update bootstrap allowlists for Sales, Finance, CEO notification/budget/token/report paths.
- [ ] Add tests that assert the allowlists include the workflow task types.

### Task 2: Finance worker
- [ ] Mark Finance implemented in `run_agents.py`.
- [ ] Add Finance to `run_single_agent.py` canonical names and runner.
- [ ] Fix Finance router API calls if needed.
- [ ] Write artifacts for token top-up, budget approval, PL, forecast, revenue, and audit handlers.
- [ ] Add tests for Finance import, run-list visibility, token ownership behavior, and artifact writing.

### Task 3: Sales worker
- [ ] Fix invalid imports in `sales-agents/sales_agent.py`.
- [ ] Add router-backed polling and ack/nack lifecycle.
- [ ] Submit revenue logs to Finance through Enterprise Router.
- [ ] Write artifacts for qualification, pitch, close, upsell, pipeline, and demo work.
- [ ] Mark Sales implemented in `run_agents.py` and route in `run_single_agent.py`.
- [ ] Add tests for Sales import, run-list visibility, and artifact writing.

### Task 4: Advisor and Marketing artifact gaps
- [ ] Add Strategic Advisor markdown artifacts for strategy reviews.
- [ ] Ensure Marketing writes an artifact for `PM_REPORT` as well as launch campaigns.
- [ ] Add tests for both artifact paths.

### Task 5: Automated workflow proof
- [ ] Add/extend a test that seeds a realistic workflow and verifies router messages and artifact records across multiple agents where feasible without long-running processes.
- [ ] Run targeted pytest files.
- [ ] Run `python -m py_compile` for changed agent files.
