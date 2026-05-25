# PM Agent Logic Structure

## Source of Truth
- Based on `agents.md` and `pm-agents/pm_agent.py`.
- Uses router transport helpers from `agent_transport.py`.

## State Machine
1. `IDLE`
- Pull inbox messages for `PM`.
- In router mode: loop `receive("PM")` until empty, then process local batch.

2. `BUSY`
- Process one fetched message at a time.
- Rule: while handling current message, do not pull new messages.

3. `PUSH_OUTPUT`
- After roadmap/feature processing, push outputs to router:
  - `LAUNCH_CAMPAIGN` -> `Marketing`
  - `PM_REPORT` -> `Marketing`
  - `FEATURE_RESPONSE` -> requesting sender

4. `COMPLETE_SUCCESS`
- Ack processed message (`ack(message_id, "PM")`).

5. `COMPLETE_FAILURE`
- Nack processed message (`nack(message_id, "PM", reason)`).

## Pull Rules
- Pull only before entering per-message handler.
- No nested pull during `handle_define_roadmap` or `handle_feature_request`.

## Push Rules (for UI visibility)
- All PM outputs must be sent through router `submit(...)`, never side-channel only.
- Keep `context.project_id` on outbound envelopes to support UI correlation.
- Router submit/fetch/ack/nack events are expected to drive observability UI.

## Task Routing Notes
- Handles:
  - `DEFINE_Q2_ROADMAP`
  - `REQUEST_FEATURES`
- Unhandled tasks: warn and still complete ack path unless handler throws.

