# Marketing Agent Logic Structure

## Source of Truth
- Based on `agents.md` and `marketing-agents/marketing_agent.py`.
- Uses `agent_transport` receive/submit/ack/nack on enterprise router.

## State Machine
1. `IDLE`
- Pull messages for `Marketing` until queue empty.

2. `BUSY`
- Process current message.
- Rule: do not pull another prompt while handling current campaign/report task.

3. `PUSH_OUTPUT`
- If budget exceeds threshold:
  - push `BUDGET_APPROVAL` -> `CEO`
- Else:
  - push `CAMPAIGN_LAUNCHED` -> `Sales`

4. `COMPLETE_SUCCESS`
- Ack current inbound envelope.

5. `COMPLETE_FAILURE`
- Nack current inbound envelope with failure reason.

## Pull Rules
- Pull only in idle/batch-fetch phase.
- No pull during campaign planning/saving/output generation.

## Push Rules (for UI visibility)
- Push only through router `submit(...)` so UI sees lifecycle events.
- Include `project_id` in context where available for cross-page joins.
- Use structured payloads (`budget`, `expected_leads`, `channel_mix`) for dashboard compatibility.

## Task Routing Notes
- Handles:
  - `LAUNCH_CAMPAIGN`
  - `PM_REPORT`
- Unhandled tasks are logged and then acked unless exception occurs.

