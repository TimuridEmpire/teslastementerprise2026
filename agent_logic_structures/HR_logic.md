# HR Agent Logic Structure

## Source of Truth
- Based on `agents.md` and `hr-agents/hr_agent.py`.
- Uses direct `EnterpriseRouterClient` operations.

## State Machine
1. `IDLE`
- Worker polls router for one HR message (`fetch_next("HR")`).

2. `BUSY`
- Record interaction in backlog.
- Run supervisor logic (`callSupervisor` or injected handler).
- Rule: worker does not fetch next prompt until current one is resolved.

3. `PUSH_OUTPUT`
- Optional outbound message pushes (example: `MINT_TOKENS` request to CEO via `submit_envelope`).

4. `COMPLETE_SUCCESS`
- Ack current message (`ack_message(message_id, "HR")`).

5. `COMPLETE_FAILURE`
- Nack current message (`nack_message(message_id, "HR", reason)`).

## Pull Rules
- One-message pull per processing cycle.
- No concurrent pull inside same worker thread while processing task.

## Push Rules (for UI visibility)
- HR-generated requests/actions must be submitted through router.
- Include provenance/routing hints where relevant (`provenance_source`, `provenance_agent`) for audit clarity.
- UI should read router audit and queue events; backlog is supplemental local trace.

## Task Routing Notes
- Typical inbound task: `TALENT_REALLOCATION`.
- Can emit token-related outbound task: `MINT_TOKENS` to CEO.

