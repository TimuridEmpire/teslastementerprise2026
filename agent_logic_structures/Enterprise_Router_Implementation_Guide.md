# Enterprise Router Implementation Guide

This guide is the contract for teams implementing agent runtime logic. The router is the required runtime path for agent-to-agent communication. The local `MessageBus` and local backlog tables are only supplemental test/demo traces unless explicitly marked as offline demo mode.

## Mental Model

The Enterprise Router is a FastAPI server that owns:

- agent registration and API keys
- message submission
- queue leasing
- ack/nack lifecycle
- audit events
- website-visible queue, audit, and artifact data

Agents do not call each other directly. Each agent polls its own router queue, processes one leased message, sends any downstream messages through the router, writes an artifact when it produces a deliverable, and then acks or nacks the leased source message.

The standard lifecycle is:

```text
IDLE -> fetch one message -> BUSY -> optionally submit outputs/artifacts -> ack or nack -> IDLE
```

## Runtime Environment

Every runtime worker needs:

```powershell
$env:ENTERPRISE_ROUTER_URL="http://localhost:8000"
$env:ENTERPRISE_AGENT_NAME="<router agent name>"
$env:ENTERPRISE_AGENT_API_KEY="<issued key for that agent>"
```

The multi-agent runner can also use per-agent key variables:

```powershell
$env:CEO_AGENT_API_KEY="<CEO key>"
$env:PM_AGENT_API_KEY="<PM key>"
$env:MARKETING_AGENT_API_KEY="<Marketing key>"
$env:HR_AGENT_API_KEY="<HR key>"
$env:ENGINEERING_AGENT_API_KEY="<Engineering key>"
$env:ADVISOR_AGENT_API_KEY="<Strategic Advisor key>"
```

Generate local keys with:

```powershell
python .\scripts\setup_local_runtime.py --write-website-env
. .\.router_keys.ps1
```

## Message Envelope Shape

All router messages must use `message_schema.Message`.

```python
from message_schema import Message

envelope = Message.create(
    sender="PM",
    recipient="Marketing",
    task_type="LAUNCH_CAMPAIGN",
    context={
        "run_id": "demo-001",
        "project_id": "q2-roadmap",
        "source_message_id": "msg-abc123",
    },
    payload={
        "campaign_name": "Q2 Launch",
        "budget": 25000,
        "expected_leads": 120,
    },
).to_dict()
```

Required envelope fields are:

- `id`
- `timestamp`
- `sender`
- `recipient`
- `task_type`
- `context`
- `payload`
- `status`
- `error`

Use `context` for correlation metadata and `payload` for the actual business request/result.

## Preferred Pull/Push API: `agent_transport.py`

Most agents should use `agent_transport.py`. It wraps `EnterpriseRouterClient`, validates router configuration, and keeps the code consistent across teams.

### Pull One Message

```python
from agent_transport import receive

envelope = receive("PM")
if envelope is None:
    return False

message_id = str(envelope["id"])
task_type = str(envelope["task_type"])
payload = envelope.get("payload", {})
context = envelope.get("context", {})
```

### Ack or Nack

Ack only after processing and output submission are complete:

```python
from agent_transport import ack, nack

try:
    handle_message(envelope)
except Exception as exc:
    nack(message_id, "PM", reason=str(exc))
    return True

ack(message_id, "PM")
return True
```

### Send Output To Another Agent

```python
from agent_transport import delegate

delegate(
    sender="PM",
    recipient="Marketing",
    task_type="PM_REPORT",
    context={
        "run_id": context.get("run_id"),
        "project_id": context.get("project_id"),
        "source_message_id": message_id,
    },
    payload={
        "summary": "Roadmap is ready for launch planning.",
        "features": ["Router outputs", "Agent artifacts"],
    },
    routing_hints={
        "urgency": "normal",
        "provenance_source": "pm_agent",
        "provenance_agent": "PM",
        "dedupe_key": f"{context.get('run_id')}:{message_id}:pm-report",
    },
)
```

### Minimal Worker Loop

```python
import time
from agent_transport import ack, nack, receive


def process_one() -> bool:
    envelope = receive("PM")
    if envelope is None:
        return False

    message_id = str(envelope["id"])
    try:
        handle_message(envelope)
    except Exception as exc:
        nack(message_id, "PM", reason=str(exc))
        return True

    ack(message_id, "PM")
    return True


while True:
    if not process_one():
        time.sleep(2)
```

## Direct Client API: `EnterpriseRouterClient`

Use `EnterpriseRouterClient` when an agent already has direct router code or needs access to raw queue-item metadata.

```python
from enterprise_router_client import EnterpriseRouterClient

client = EnterpriseRouterClient.from_env(agent_name="CEO")

envelope = client.fetch_next("CEO")
if envelope:
    message_id = str(envelope["id"])
    try:
        result = handle_message(envelope)
    except Exception as exc:
        client.nack_message(message_id, "CEO", reason=str(exc))
    else:
        client.ack_message(message_id, "CEO")
```

To submit:

```python
message_id = client.submit_envelope(
    envelope,
    routing_hints={
        "urgency": "high",
        "provenance_source": "ceo_agent",
        "provenance_agent": "CEO",
        "dedupe_key": "run-001:ceo:strategy-review",
    },
)
```

## Writing Website-Visible Outputs

Queue and audit data prove that work moved through the system. Markdown artifacts prove what the agent produced.

Whenever an agent creates a meaningful deliverable, call `write_agent_artifact(...)`.

```python
from enterprise_router.agent_artifacts import write_agent_artifact

artifact = write_agent_artifact(
    "CEO",
    title="CEO Executive Summary",
    artifact_type="strategy",
    body=(
        "## Decision\n\n"
        "Invest in router-visible agent outputs.\n\n"
        "## Rationale\n\n"
        "The website needs proof of work, not only queue lifecycle events."
    ),
    metadata={
        "run_id": context.get("run_id"),
        "project_id": context.get("project_id"),
    },
    source_message_id=message_id,
    source_task_type=task_type,
)
```

This writes:

- `artifacts/<agent-slug>/*.md`
- `artifacts/index.jsonl`

The website reads artifacts through:

```text
GET /artifacts?agent=<agent name>&limit=20
GET /artifacts/{artifact_id}
```

Do not make the website read files directly.

## Recommended Result Payload Shape

When an agent sends a result envelope back to the requester, use a structured payload:

```python
payload = {
    "status": "done",
    "summary": "Campaign plan created.",
    "artifact_id": artifact["artifact_id"],
    "details": {
        "budget": 25000,
        "expected_leads": 120,
    },
    "next_actions": [
        "Marketing reviews channel mix",
        "CEO approves budget if above threshold",
    ],
}
```

If processing fails but the agent catches the failure and reports it, use:

```python
payload = {
    "status": "error",
    "summary": "Could not generate campaign plan.",
    "error": "Missing project_id in context.",
    "recoverable": True,
}
```

Use `nack(...)` only when the source message should be retried or dead-lettered by the router. Use a successful result envelope with `status="error"` when the task is complete but the business result is a failure report.

## Current Router Agent Names And Inbound Tasks

These names must match registration exactly.

| Agent | Router name | Current inbound task types |
|---|---|---|
| CEO | `CEO` | `CEO_PING`, `CEO_CHAT`, `CEO_REASONING_LOOP`, `CEO_METRICS`, `MINT_TOKENS`, `BUDGET_APPROVAL`, `MANAGER_INTERVENTION`, `IMPLEMENT_FEATURE`, `STRATEGY_REVIEW_RESULT` |
| PM | `PM` | `DEFINE_Q2_ROADMAP`, `REQUEST_FEATURES`, `MANAGER_INTERVENTION` |
| Marketing | `Marketing` | `LAUNCH_CAMPAIGN`, `PM_REPORT`, `MANAGER_INTERVENTION` |
| HR | `HR` | `TALENT_REALLOCATION`, `MANAGER_INTERVENTION` |
| Engineering | `Engineering` | `IMPLEMENT_FEATURE`, `FEATURE_RESPONSE`, `MANAGER_INTERVENTION` |
| Strategic Advisor | `Strategic Advisor` | `STRATEGY_REVIEW_REQUEST`, `CEO_PROPOSAL_FOR_REVIEW`, `MANAGER_INTERVENTION` |
| Sales | `Sales` | `CAMPAIGN_LAUNCHED`, `MANAGER_INTERVENTION` |
| Finance | `Finance` | `BUDGET_APPROVAL`, `MANAGER_INTERVENTION` |

If a team needs a new inbound task type, update the registration allowlist in `scripts/setup_local_runtime.py` and `scripts/bootstrap_router_agents.py` before submitting that message type.

## Agent-Specific Implementation Checklist

### CEO

- Pull with `EnterpriseRouterClient.from_env(agent_name="CEO")` or `process_one_router_message()`.
- Route by `on_bus_envelope(...)`.
- For `CEO_REASONING_LOOP`, write a `strategy` artifact.
- For decisions that need another team, submit an envelope to that team.
- Ack after artifact/result submission succeeds.

### PM

- Pull with `receive("PM")`.
- Handle `DEFINE_Q2_ROADMAP` and `REQUEST_FEATURES`.
- Write a roadmap/product artifact when the roadmap or feature response is created.
- Send `LAUNCH_CAMPAIGN` and `PM_REPORT` to `Marketing` through `delegate(...)`.
- Include `context.project_id` and `context.source_message_id`.
- Ack after downstream Marketing messages and artifacts are written.

### Marketing

- Pull with `receive("Marketing")`.
- Handle `LAUNCH_CAMPAIGN` and `PM_REPORT`.
- Write a campaign artifact with budget, channel mix, expected leads, and launch recommendation.
- If budget approval is needed, send `BUDGET_APPROVAL` to `CEO`.
- Otherwise send `CAMPAIGN_LAUNCHED` to `Sales`.
- Ack after outbound message submission succeeds.

### HR

- Pull one message at a time with `EnterpriseRouterClient.fetch_next("HR")` or `receive("HR")`.
- Handle `TALENT_REALLOCATION` and `MANAGER_INTERVENTION`.
- Write a staffing artifact with role changes, rationale, and risks.
- If token minting or executive approval is needed, send `MINT_TOKENS` to `CEO`.
- Ack after artifact/output submission succeeds.

### Engineering

- Pull with `receive("Engineering")`.
- Handle `IMPLEMENT_FEATURE` and legacy `generate_code`.
- Write an engineering artifact with generated files, test status, and review notes.
- Send `FEATURE_RESPONSE` to the original requester with `status`, `artifact_id`, and error details if any.
- Ack only after response submission succeeds.

### Strategic Advisor

- Pull with `EnterpriseRouterClient.fetch_next("Strategic Advisor")` or `process_one_router_message()`.
- Handle `STRATEGY_REVIEW_REQUEST`, `CEO_PROPOSAL_FOR_REVIEW`, and `*_FOR_REVIEW`.
- Write an advisory artifact with assessment, alignment, risks, and recommended action.
- Send `STRATEGY_REVIEW_RESULT` to `CEO` or the original sender.
- Ack after result submission succeeds.

## Common Mistakes To Avoid

- Do not fetch a second message while still processing the current message.
- Do not ack before output messages and artifacts are written.
- Do not write only local files when the website needs to see a result.
- Do not send messages with a `sender` that does not match the authenticated API key.
- Do not invent router names; use exact registered names.
- Do not add a new `task_type` without updating the registration allowlist.
- Do not expose absolute artifact paths to the browser.
- Do not write to a database directly for runtime agent communication; always go through the router.

