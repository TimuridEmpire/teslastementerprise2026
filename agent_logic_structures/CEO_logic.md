# CEO Agent Logic Structure

## Source of Truth
- Based on `agents.md` and `ceo-agents/ceo_agent.py`.
- Runtime transport is `enterprise_router` via `EnterpriseRouterClient`.
- Implementation details for pulling, posting, ack/nack, and artifact output are in `agent_logic_structures/Enterprise_Router_Implementation_Guide.md`.

## State Machine
1. `IDLE`
- Condition: no active task in progress.
- Action: pull exactly one message from router queue for `CEO` (`fetch_next("CEO")`).

2. `BUSY`
- Condition: one message has been fetched and is being processed.
- Rule: do not pull another message while this task is running.
- Action: route by `task_type` in `on_bus_envelope`.

3. `COMPLETE_SUCCESS`
- Action: `ack_message(message_id, "CEO")`.
- Optional output push: if task requires downstream action, send new envelope(s) with `submit_envelope(...)`.

4. `COMPLETE_FAILURE`
- Action: `nack_message(message_id, "CEO", reason=...)`.
- No additional pull until failure path is finished.

## Pull Rules
- Pull only in `IDLE`.
- Pull one-at-a-time (`process_one_router_message` pattern).
- If queue empty, remain `IDLE` and sleep/poll.

## Push Rules (for UI visibility)
- Push outbound decisions/tasks to router using `send_router_envelope(...)` or `submit_envelope(...)`.
- Ensure payload contains actionable business context so UI pages can render meaningful state.
- Always rely on router audit/queue lifecycle for visibility (submit -> fetch -> ack/nack).

## Task Routing Notes
- Handles `CEO_STRATEGIC_CYCLE`, `CEO_ENVIRONMENT_SIGNAL`, `CEO_PING`, `CEO_GATHER_ONLY`, `CEO_CHAT`, `CEO_REASONING_LOOP`, `CEO_METRICS`, `MINT_TOKENS`.
- Unknown task types are acknowledged with a no-op note (still acked after handler returns).

