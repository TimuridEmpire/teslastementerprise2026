# Engineering Agent Logic Structure

## Source of Truth
- Based on `agents.md` and `eng-agents/engineering_agent.py`.
- Router path is primary; legacy Mongo path only for offline demo.
- Implementation details for pulling, posting, ack/nack, and artifact output are in `agent_logic_structures/Enterprise_Router_Implementation_Guide.md`.

## State Machine
1. `IDLE`
- Poll for one message (`receive("Engineering")` through `claim_next_message`).

2. `BUSY`
- Build spec from inbound task (`generate_code` or `IMPLEMENT_FEATURE`).
- Execute review/iterate pipeline.
- Rule: no additional pull while current generation task is running.

3. `PUSH_OUTPUT`
- Push response envelope to original sender via router `submit(response)`:
  - `status=done` with result payload
  - or `status=error` with error detail

4. `COMPLETE_SUCCESS`
- Ack source message (`ack(message_id, "Engineering")`).

5. `COMPLETE_FAILURE`
- If processing throws, response carries error; source message handling follows failure path.

## Pull Rules
- Single-message polling loop.
- Skip pull while active generation/review iteration is in progress.

## Push Rules (for UI visibility)
- Always submit response through router transport in online mode.
- Keep `task_type` consistent with request so UI/audit correlation stays intact.
- Router lifecycle events should represent engineering job flow in observability pages.

## Task Routing Notes
- Handles:
  - `generate_code` (legacy format)
  - `IMPLEMENT_FEATURE` (PM-oriented format)
- Unknown task type returns structured error response.

