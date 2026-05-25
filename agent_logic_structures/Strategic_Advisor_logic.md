# Strategic Advisor Agent Logic Structure

## Source of Truth
- Based on `agents.md` and `ceo-agents/advisor_agent.py`.
- Uses enterprise router pull/process/ack cycle.
- Implementation details for pulling, posting, ack/nack, and artifact output are in `agent_logic_structures/Enterprise_Router_Implementation_Guide.md`.

## State Machine
1. `IDLE`
- Pull one message for `Strategic Advisor` (`fetch_next("Strategic Advisor")`).

2. `BUSY`
- Evaluate proposal envelope.
- Rule: do not pull while actively evaluating or preparing response.

3. `PUSH_RESPONSE`
- For review tasks, push `STRATEGY_REVIEW_RESULT` back to CEO via router `submit(...)`.

4. `COMPLETE_SUCCESS`
- Ack current message (`ack_message(...)`).

5. `COMPLETE_FAILURE`
- Nack current message (`nack_message(..., reason)`).

## Pull Rules
- Pull only when not processing another envelope.
- Single-message processing loop (`process_one_router_message`).

## Push Rules (for UI visibility)
- Always push advisory outcomes as structured envelopes:
  - `recipient`: CEO (or original sender)
  - `task_type`: `STRATEGY_REVIEW_RESULT`
  - payload includes `is_aligned`, `assessment`, `recommended_action`
- Router audit events should be treated as UI truth for review lifecycle.

## Task Routing Notes
- Review tasks include `STRATEGY_REVIEW_REQUEST`, `CEO_PROPOSAL_FOR_REVIEW`, and `*_FOR_REVIEW`.
- Non-review tasks are acknowledged with informational no-op response.

