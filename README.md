# TESLA STEM Enterprise 2026

TESLA STEM Enterprise 2026 is a router-backed multi-agent enterprise simulation. The project combines:

- A Python backend of autonomous department agents.
- A FastAPI `enterprise_router` service that acts as the shared communication layer.
- A Next.js website that shows health, queues, audit activity, artifacts, and operator controls.
- A test suite that verifies message schemas, router behavior, agent integrations, storage, and local workflows.

The most important idea in this repository is simple: agents do not directly write to each other's queues. In normal runtime, they communicate through the Enterprise Router over HTTP. The router authenticates each agent, validates what that agent is allowed to receive, stores queued work, leases messages to workers, records ack/nack outcomes, and exposes live state to the website.

This README is intentionally detailed. It is written for both technical contributors and non-technical stakeholders who need to understand what the system is, how the pieces fit, and how information moves through the unified agent organization.

## Table of Contents

1. [Project at a Glance](#project-at-a-glance)
2. [Core Architecture](#core-architecture)
3. [Important Files and Directories](#important-files-and-directories)
4. [Unified Agent System](#unified-agent-system)
5. [Agent Responsibilities](#agent-responsibilities)
6. [How Agents Talk to Each Other](#how-agents-talk-to-each-other)
7. [Enterprise Router Deep Dive](#enterprise-router-deep-dive)
8. [Frontend and Backend Intersection](#frontend-and-backend-intersection)
9. [Message Envelope Standard](#message-envelope-standard)
10. [Artifacts and Outputs](#artifacts-and-outputs)
11. [Live vs Mock Data](#live-vs-mock-data)
12. [Setup](#setup)
13. [Running the System Locally](#running-the-system-locally)
14. [Website Commands](#website-commands)
15. [Testing](#testing)
16. [Docker and Local LLM Notes](#docker-and-local-llm-notes)
17. [Environment Variables](#environment-variables)
18. [Storage Backends](#storage-backends)
19. [Common Workflows](#common-workflows)
20. [Troubleshooting](#troubleshooting)
21. [Security and Privacy Notes](#security-and-privacy-notes)
22. [Developer Notes](#developer-notes)
23. [Graphify Architecture Notes](#graphify-architecture-notes)

## Project at a Glance

The repository models an enterprise made of specialized software agents. Each agent has a department-like role. The CEO sets strategy and delegates. PM converts strategy into plans and routes work. Engineering implements or simulates implementation. HR handles staffing and thread allocation. Marketing plans campaigns. The Strategic Advisor reviews CEO proposals for alignment.

The router is the operational center. It does not decide business strategy. Instead, it provides the shared communication infrastructure that lets the agents act as one coordinated system.

Current implemented runtime workers:

- `CEO`
- `PM`
- `Marketing`
- `HR`
- `Engineering`
- `Strategic Advisor`

Registered but not implemented as long-running workers in this codebase:

- `Sales`
- `Finance`

The website knows about Sales and Finance because they are part of the intended enterprise model, but `run_agents.py` skips them because this repository does not currently include active worker implementations for those departments.

## Core Architecture

At a high level, the system has five layers.

### 1. Agent Layer

The agent layer contains the department workers. These are Python modules that poll the router, process one message at a time, and optionally create follow-up messages.

Key files:

- `ceo-agents/ceo_agent.py`
- `ceo-agents/advisor_agent.py`
- `pm-agents/pm_agent.py`
- `marketing-agents/marketing_agent.py`
- `hr-agents/hr_agent.py`
- `eng-agents/engineering_agent.py`
- `run_agents.py`
- `run_single_agent.py`

### 2. Router Layer

The router layer is the shared API and persistence boundary. It owns registration, API keys, queueing, leases, retries, audit records, and artifact read endpoints.

Key files:

- `enterprise_router/api.py`
- `enterprise_router/service.py`
- `enterprise_router/models.py`
- `enterprise_router/router_storage.py`
- `enterprise_router/sqlite_storage.py`
- `enterprise_router/mongo_storage.py`
- `enterprise_router/config.py`
- `enterprise_router/agent_artifacts.py`

### 3. Transport and Message Layer

The transport layer gives agents a consistent way to build, validate, submit, fetch, ack, and nack messages.

Key files:

- `message_schema.py`
- `enterprise_router_client.py`
- `agent_transport.py`
- `message_bus.py`
- `agent_backlog.py`
- `inter_agent_api.py`
- `inter_agent_mongo.py`

In normal runtime, `enterprise_router_client.py` and `agent_transport.py` are the main route. `message_bus.py` and legacy Mongo paths are reserved for explicit offline/demo scenarios.

### 4. Website Layer

The website is a Next.js app that displays the enterprise state and lets a manager send router-backed interventions.

Key files:

- `website/app/dashboard/page.tsx`
- `website/app/observability/page.tsx`
- `website/app/chat/page.tsx`
- `website/app/agents/[agent]/page.tsx`
- `website/app/messages/page.tsx`
- `website/app/onboarding/page.tsx`
- `website/lib/api.ts`
- `website/lib/hooks.ts`
- `website/lib/live-metrics.ts`
- `website/lib/chat-router.ts`
- `website/components/chat/*`
- `website/components/layout/*`

### 5. Test and Simulation Layer

The tests validate the router, agents, schemas, CLI behavior, and integrated flows.

Key files:

- `tests/test_enterprise_router.py`
- `tests/test_enterprise_router_e2e.py`
- `tests/test_enterprise_router_client.py`
- `tests/test_agent_transport_runtime.py`
- `tests/test_ceo_router_integration.py`
- `tests/test_hr_router_integration.py`
- `tests/test_engineering_light_demo.py`
- `tests/standard_scenario_test.py`
- `pytest.ini`

## Important Files and Directories

### Root Python Runtime

`run_agents.py`

Starts multiple implemented workers. It checks for agent API keys, skips missing workers, and starts one child process per runnable agent.

`run_single_agent.py`

Starts one worker. `run_agents.py` uses this internally. It maps friendly names like `advisor` or `eng` to canonical router names like `Strategic Advisor` and `Engineering`.

`enterprise_router_client.py`

Small HTTP client for the router. It reads router URL, agent name, API key, and timeout from the environment. It submits envelopes, fetches the next message, peeks queues, and performs ack/nack operations.

`agent_transport.py`

Shared transport helper used by department agents. It enforces the rule that runtime communication uses the Enterprise Router unless `ENTERPRISE_ROUTER_OFFLINE_DEMO=1` is intentionally set.

`message_schema.py`

Single source of truth for the inter-agent message envelope. All major messaging paths normalize or validate messages through this module.

`agent_backlog.py`

Local execution log. This is useful for debugging and local history, but it is not the shared queue of record. The router is the source of truth for live agent-to-agent delivery.

`enterprise_paths.py`

Centralizes local paths and environment-based persistence settings for backlog DBs, JSONL logs, MongoDB, router URL, and artifacts.

### Enterprise Router Package

`enterprise_router/api.py`

FastAPI application. Exposes health, registrations, agent management, message submit/fetch/ack/nack, queue inspection, audit log, manager intervention, and artifact endpoints.

`enterprise_router/service.py`

Business logic for the router. Handles registration approval, API key authentication, access checks, queue maintenance, priority, TTL, dedupe, leases, retries, dead-lettering, and audit logging.

`enterprise_router/models.py`

Dataclasses for router records: `RegistrationRequest`, `AgentApiKeyRecord`, `AgentRecord`, `RoutingHints`, and `QueuedMessage`.

`enterprise_router/router_storage.py`

Storage interface and factory for router persistence.

`enterprise_router/sqlite_storage.py`

SQLite implementation of router persistence. This is the normal local-development backend.

`enterprise_router/mongo_storage.py`

MongoDB implementation of the same storage contract. This is optional and should be used only when intentionally running the router with MongoDB.

`enterprise_router/agent_artifacts.py`

Writes markdown deliverables from agents into `artifacts/`, indexes them, and serves public-safe artifact metadata/content through the router API.

### Agent Logic and Planning Notes

`agent_logic_structures/`

Contains design notes and pseudocode for CEO, PM, HR, Marketing, Engineering, Strategic Advisor, and router implementation concepts. These files are useful for understanding intended behavior and future roadmap.

`agents.md`

Short handoff document that summarizes the repo purpose, architecture, run flow, environment notes, and common issues.

### Website

`website/package.json`

Next.js scripts and dependencies.

`website/lib/api.ts`

The website API client. It calls the router over HTTP. It does not read MongoDB or SQLite directly.

`website/lib/hooks.ts`

Polling hooks for health, agents, audit events, registrations, queues, and artifacts.

`website/lib/live-metrics.ts`

Transforms router audit and queue information into dashboard-friendly metrics.

`website/app/*`

Next.js route pages for dashboard, chat, agents, messages, resources, settings, workflows, simulation, lab, onboarding, and observability.

### Graphify Output

`../graphify-out/GRAPH_REPORT.md`

Architecture graph report generated from the codebase. It identifies high-connectivity modules and communities, including Enterprise Router API, Router Client, Agent Transport, CEO Agent Core, PM Agent Tools, Website API Client, Live Metrics, and Run Agents CLI.

`../graphify-out/graph.html`

Interactive graph visualization.

`../graphify-out/graph.json`

Machine-readable architecture graph.

## Unified Agent System

The system behaves like a small company:

1. A user, onboarding flow, script, or manager intervention creates a business request.
2. The request enters the Enterprise Router as a message.
3. The router stores the message in the recipient's queue.
4. The recipient agent fetches one message, processes it, and marks it complete or failed.
5. The agent may create follow-up messages for other departments.
6. Each follow-up returns to the router, where the same queueing and audit process repeats.
7. The website watches router health, audit records, queues, and artifacts to show what happened.

This creates a unified system because all major agents share the same communication contract:

- Same message envelope.
- Same router API.
- Same queue lifecycle.
- Same audit log.
- Same artifact surface for completed work.
- Same local runtime setup process.

The agents are autonomous in the sense that each agent decides what to do when it receives a supported `task_type`. They are coordinated because no agent needs private access to another agent's memory or local files to communicate. The router is the neutral exchange point.

## Agent Responsibilities

### CEO Agent

Primary file: `ceo-agents/ceo_agent.py`

Router name: `CEO`

Role: strategic leader and central decision-maker.

What the CEO does:

- Receives high-level business prompts.
- Executes strategic reasoning loops.
- Gathers simulated department reports.
- Calls a local Ollama/Mistral model for strategic analysis and summaries when available.
- Writes CEO strategy artifacts.
- Delegates strategy to PM through `CEO_STRATEGY_DIRECTIVE`.
- Receives PM and Engineering updates.
- Handles CEO-specific tasks such as `CEO_CHAT`, `CEO_REASONING_LOOP`, `CEO_METRICS`, `CEO_GATHER_ONLY`, `CEO_STRATEGIC_CYCLE`, and `CEO_ENVIRONMENT_SIGNAL`.
- Manages distribution token scenarios in local/demo message-bus flows.
- Can process `MINT_TOKENS` requests from HR.

Important CEO outputs:

- Strategy artifacts.
- `CEO_STRATEGY_DIRECTIVE` messages to PM.
- Status responses and audit-visible message lifecycle events.

Important CEO safety behavior:

- The CEO class includes child-safety and local-audio privacy checks.
- If child-safety signals indicate children are nearby, certain strategic/resource allocation operations can be rerouted to a Legal Compliance Agent concept.
- Audio-policy context can require local-only processing and disallow external audio storage.

### PM Agent

Primary file: `pm-agents/pm_agent.py`

Router name: `PM`

Role: product planning and coordination.

What PM does:

- Converts CEO strategy into execution plans.
- Creates and stores project records.
- Generates and prioritizes feature lists using PM tools.
- Writes roadmap and strategy-routing artifacts.
- Sends staffing needs to HR.
- Sends implementation work to Engineering.
- Sends reports back to CEO.
- Handles Engineering feature responses and closes the loop back to CEO.

Supported tasks include:

- `DEFINE_Q2_ROADMAP`
- `REQUEST_FEATURES`
- `CEO_STRATEGY_DIRECTIVE`
- `FEATURE_RESPONSE`
- `MANAGER_INTERVENTION`

Important PM outputs:

- Roadmap artifacts.
- `TALENT_REALLOCATION` messages to HR.
- `IMPLEMENT_FEATURE` messages to Engineering.
- `PM_REPORT` messages to CEO.
- In roadmap flows, downstream messages can also route to Marketing.

### Marketing Agent

Primary file: `marketing-agents/marketing_agent.py`

Router name: `Marketing`

Role: campaign planning and marketing execution.

What Marketing does:

- Receives campaign launch requests.
- Plans campaigns based on product and feature payloads.
- Estimates campaign budget and expected leads.
- Requests CEO budget approval if budget exceeds a configured threshold.
- Saves campaign information through PM storage helpers.
- Writes campaign brief artifacts.
- Sends campaign launch notifications to Sales when campaign budgets do not require executive approval.
- Records PM report events.

Supported tasks include:

- `LAUNCH_CAMPAIGN`
- `PM_REPORT`
- `THREAD_ALLOCATION`
- `MANAGER_INTERVENTION`

Important Marketing outputs:

- `BUDGET_APPROVAL` messages to CEO when a campaign exceeds the approval threshold.
- `CAMPAIGN_LAUNCHED` messages to Sales when a campaign can proceed.
- Campaign brief artifacts.

Current limitation:

- Sales is registered but does not currently have a running worker in this repository, so Sales-targeted messages can be queued and observed but not consumed by a local Sales worker unless one is added.

### HR Agent

Primary file: `hr-agents/hr_agent.py`

Router name: `HR`

Role: staffing, agent capacity, and organizational operations.

What HR does:

- Processes staffing and talent reallocation requests.
- Maintains a local view of desired agent counts.
- Can route thread allocation instructions to other agents.
- Can request distribution tokens from CEO.
- Writes HR staffing artifacts for `TALENT_REALLOCATION` messages.
- Runs with multiple polling threads in its standalone entrypoint.

Supported tasks include:

- `TALENT_REALLOCATION`
- `THREAD_ALLOCATION`
- `MANAGER_INTERVENTION`

Important HR outputs:

- `THREAD_ALLOCATION` messages to departments.
- `MINT_TOKENS` requests to CEO.
- HR staffing review artifacts.

### Engineering Agent

Primary file: `eng-agents/engineering_agent.py`

Router name: `Engineering`

Role: implementation, code generation, testing, and technical reporting.

What Engineering does:

- Receives feature implementation requests.
- Builds an implementation specification from the incoming message.
- In full mode, uses CrewAI roles for lead developer, developer, and tester.
- Generates files into `OUTPUT_DIR`.
- Runs tests for generated code.
- Iterates fixes until tests pass or the configured iteration limit is reached.
- Writes Engineering artifacts describing generated files, test status, review notes, and errors.
- Sends `FEATURE_RESPONSE` back to the requesting agent, usually PM.

Supported tasks include:

- `IMPLEMENT_FEATURE`
- `generate_code`
- `FEATURE_RESPONSE`
- `THREAD_ALLOCATION`
- `MANAGER_INTERVENTION`

Light demo mode:

- If CrewAI dependencies are missing, `run_agents.py` can start Engineering in deterministic light-demo mode.
- Light-demo mode consumes `IMPLEMENT_FEATURE`, writes an artifact, sends `FEATURE_RESPONSE`, and acks the router message, but it does not generate real code.

Full mode:

- Requires `crewai` and `crewai_tools`.
- Uses Ollama-compatible local LLM configuration.
- Can optionally commit generated output to a configured Git repository.

### Strategic Advisor Agent

Primary file: `ceo-agents/advisor_agent.py`

Router name: `Strategic Advisor`

Role: strategic review and alignment check.

What the Advisor does:

- Reviews CEO proposals or strategy-review requests.
- Compares proposals against a core strategy string.
- Returns an advisory response to the proposal sender.
- Flags simple strategic drift, such as hardware/manufacturing proposals when the strategy is software-focused.

Supported tasks include:

- `STRATEGY_REVIEW_REQUEST`
- `CEO_PROPOSAL_FOR_REVIEW`
- Any task ending in `_FOR_REVIEW`
- `MANAGER_INTERVENTION`

Important Advisor outputs:

- `STRATEGY_REVIEW_RESULT` messages back to CEO or the original sender.

### Sales Agent

Router name: `Sales`

Role: intended sales follow-through for campaigns and customer-facing activity.

Current state:

- Sales is registered by setup scripts.
- The website can display Sales as an enterprise participant.
- This repository does not currently include an active Sales worker implementation used by `run_agents.py`.

Expected future behavior:

- Consume `CAMPAIGN_LAUNCHED`.
- Convert campaign outputs into pipeline or lead activity.
- Report outcomes back to CEO, PM, Marketing, or Finance.

### Finance Agent

Router name: `Finance`

Role: intended budget, forecast, ROI, and approval support.

Current state:

- Finance is registered by setup scripts.
- The website can display Finance as an enterprise participant.
- This repository includes some finance-related modules and tests, but `run_agents.py` marks Finance as missing because there is no active runtime worker wired into the launcher.

Expected future behavior:

- Consume budget and approval tasks.
- Calculate ROI and financial risk.
- Return finance reports to CEO or PM.

### Manager

Router name: `MANAGER`

Role: dashboard/operator identity rather than a normal department worker.

What Manager does:

- Submits website-originated interventions through `/manager/interventions`.
- Uses manager credentials from website environment variables.
- Lets the website queue instructions to real agents without pretending the browser is a department worker.

Current limitation:

- `MANAGER` is primarily an authenticated sender. It is not a long-running worker in `run_agents.py`.

## How Agents Talk to Each Other

Agents communicate through router messages. The usual lifecycle is:

1. Sender builds a canonical envelope with `Message.create(...)`.
2. Sender submits the envelope through `EnterpriseRouterClient` or `agent_transport.submit(...)`.
3. Router authenticates the sender using the `Authorization` bearer token and `X-Agent-Id`.
4. Router verifies that the envelope sender matches the authenticated agent.
5. Router checks the recipient's allowlist for supported task types.
6. Router stores the message with routing hints such as priority, TTL, or dedupe key.
7. Recipient worker polls its queue with `/messages/fetch-next`.
8. Router leases one message to the recipient.
9. Recipient handles the message.
10. Recipient calls ack on success or nack on failure.
11. Router records audit events for the lifecycle.

### Example CEO to PM Flow

1. Website onboarding or chat queues a `CEO_REASONING_LOOP` message.
2. CEO worker fetches the message.
3. CEO gathers simulated department data and calls the local model for strategy.
4. CEO writes a strategy artifact.
5. CEO sends `CEO_STRATEGY_DIRECTIVE` to PM.
6. PM fetches the directive.
7. PM writes a routing plan artifact.
8. PM sends `TALENT_REALLOCATION` to HR.
9. PM sends `IMPLEMENT_FEATURE` to Engineering.
10. PM sends `PM_REPORT` back to CEO.
11. HR and Engineering process their own messages.
12. Engineering sends `FEATURE_RESPONSE` to PM.
13. PM turns Engineering's response into a `PM_REPORT` for CEO.

### Example PM to Marketing Flow

1. PM receives `DEFINE_Q2_ROADMAP`.
2. PM creates a project and roadmap.
3. PM decides downstream routes.
4. PM sends `LAUNCH_CAMPAIGN` and/or `PM_REPORT` to Marketing.
5. Marketing plans the campaign.
6. Marketing either requests `BUDGET_APPROVAL` from CEO or sends `CAMPAIGN_LAUNCHED` to Sales.

### Example Advisor Flow

1. CEO or Manager sends a proposal review task to `Strategic Advisor`.
2. Advisor evaluates whether the proposal aligns with core strategy.
3. Advisor sends `STRATEGY_REVIEW_RESULT` back to the original sender.

### Why This Matters

The router-centered pattern gives the system several important properties:

- Every work item has a traceable message ID.
- Every message follows the same schema.
- Agents can be restarted without losing queued work.
- The website can observe message flow without reading private agent internals.
- Failed messages can be retried or dead-lettered.
- The system can add new agents by registering them and giving them a worker.

## Enterprise Router Deep Dive

The Enterprise Router is the most important backend component. It is both the message exchange and the operational record.

### Router Responsibilities

The router handles:

- Agent registration.
- Admin approval and rejection.
- API key issuing.
- API key hashing and validation.
- Agent status and metadata.
- Allowed task types.
- Message validation.
- Message submission.
- Queue storage.
- Priority calculation.
- TTL expiration.
- Dedupe keys.
- Message leasing.
- Ack/nack state transitions.
- Retry attempts.
- Dead-lettering after repeated failures.
- Audit logging.
- Artifact listing and artifact detail retrieval.
- Manager interventions.

### Router API Endpoints

Important endpoints:

- `GET /health`
- `POST /registrations/request`
- `POST /registrations/{agent_name}/approve`
- `POST /registrations/{agent_name}/reject`
- `GET /registrations`
- `POST /agents`
- `GET /agents`
- `POST /agents/{agent_name}/issue-api-key`
- `POST /messages`
- `GET /messages/peek`
- `POST /messages/fetch-next`
- `GET /queue/{recipient}`
- `POST /messages/{message_id}/ack`
- `POST /messages/{message_id}/nack`
- `POST /manager/interventions`
- `GET /audit`
- `GET /artifacts`
- `GET /artifacts/{artifact_id}`

### Authentication Model

Agent endpoints use:

- `Authorization: Bearer <agent-api-key>`
- `X-Agent-Id: <agent-name>`

Admin endpoints use:

- `X-Admin-Secret: <admin-secret>`

The README does not include real secret values. Local examples use placeholder development values only.

### Access Control

The router checks whether the target agent is active and whether the incoming task type is allowed for that recipient. For example:

- CEO can receive tasks like `CEO_REASONING_LOOP`, `PM_REPORT`, `MINT_TOKENS`, and `BUDGET_APPROVAL`.
- PM can receive `DEFINE_Q2_ROADMAP`, `REQUEST_FEATURES`, `CEO_STRATEGY_DIRECTIVE`, and `FEATURE_RESPONSE`.
- Marketing can receive `LAUNCH_CAMPAIGN`, `PM_REPORT`, and `THREAD_ALLOCATION`.
- HR can receive `TALENT_REALLOCATION`, `THREAD_ALLOCATION`, and `MANAGER_INTERVENTION`.
- Engineering can receive `IMPLEMENT_FEATURE`, `FEATURE_RESPONSE`, `THREAD_ALLOCATION`, and `MANAGER_INTERVENTION`.
- Strategic Advisor can receive review requests and manager interventions.

These allowlists are defined in `scripts/bootstrap_router_agents.py` and written through `scripts/setup_local_runtime.py`.

### Priority, TTL, and Dedupe

Routing hints can include:

- `priority`
- `urgency`
- `requires_response`
- `ttl_seconds`
- `dedupe_key`

If `priority` is absent, `RoutingHints.from_mapping(...)` can map urgency strings to priority numbers. Examples include `critical`, `urgent`, `high`, `normal`, `medium`, and `low`.

TTL lets messages expire if they are no longer relevant. Dedupe prevents duplicate messages for the same sender, recipient, task, and dedupe key.

### Leases, Ack, Nack, and Dead Letters

When a worker calls fetch-next, the router leases the message. The worker must then:

- `ack` when processing succeeds.
- `nack` when processing fails.

Nacked messages are retried until they hit the maximum attempt count. After repeated nacks, the router dead-letters the message.

This prevents one failing message from blocking the entire system forever while still giving transient errors a chance to recover.

### Audit Log

The audit log is the main timeline for completed work. Queues only show messages that are still waiting or currently visible. Once a worker fetches and acks/nacks a message, the message may leave the active queue view. The audit log records lifecycle events such as:

- Agent registered.
- API key issued.
- Message submitted.
- Message acked.
- Message nacked.
- Registration approved or rejected.

The website's observability page relies heavily on audit data.

## Frontend and Backend Intersection

The frontend and backend meet at the Enterprise Router API. The website does not bypass the backend by reading SQLite, MongoDB, or local files directly. That is intentional.

### What the Backend Provides

The backend provides:

- Router health.
- Registered agent records.
- Queue contents.
- Audit events.
- Artifact metadata and markdown content.
- Manager intervention endpoint.
- Agent-authenticated message operations.

### What the Website Provides

The website provides:

- Dashboard overview.
- Observability views.
- Agent queue pages.
- Agent output/artifact display.
- Manager chat/intervention UI.
- Onboarding flow that can queue a real CEO message.
- Visual summaries from live router/audit data where available.
- Mock/demo cards where live business metrics are not yet emitted by agents.

### Website API Client

`website/lib/api.ts` is the main bridge. It defines functions for:

- `api.health()`
- `api.agents.list(...)`
- `api.agents.register(...)`
- `api.messages.submit(...)`
- `api.messages.peek(...)`
- `api.messages.fetchNext(...)`
- `api.messages.ack(...)`
- `api.messages.nack(...)`
- `api.queue.list(...)`
- `api.manager.intervene(...)`
- `api.audit.list(...)`
- `api.artifacts.list(...)`
- `api.artifacts.get(...)`

### Website Polling

`website/lib/hooks.ts` provides polling hooks:

- Health every 30 seconds.
- Agents every 15 seconds.
- Audit every 8 seconds.
- Registrations every 12 seconds.
- Queue views every 4 seconds.
- Artifacts every 6 seconds.

This makes the website feel live without requiring websockets.

### Important Frontend/Backend Behavior

The website can show a message in a queue only while that message remains queued or visible. If a worker quickly fetches and acks it, the queue page may look empty. That does not mean nothing happened. Use:

- `/observability` for audit history.
- `/dashboard` for latest artifacts.
- `/agents/<agent>` for an agent's active queue and latest output.
- `/artifacts` API through the website views for completed markdown deliverables.

## Message Envelope Standard

Every inter-agent message should use the standard envelope from `message_schema.py`.

Required fields:

```json
{
  "id": "msg-12345678",
  "timestamp": "2026-01-01T00:00:00Z",
  "sender": "CEO",
  "recipient": "PM",
  "task_type": "CEO_STRATEGY_DIRECTIVE",
  "context": {},
  "payload": {},
  "status": "pending",
  "error": ""
}
```

Field meanings:

- `id`: unique message identifier.
- `timestamp`: UTC time when the envelope was created.
- `sender`: authenticated sender name.
- `recipient`: target agent name.
- `task_type`: handler key used by the recipient.
- `context`: correlation metadata, such as `run_id`, `project_id`, or `source_message_id`.
- `payload`: business data or instruction body.
- `status`: message status, usually `pending`, `in_progress`, `done`, or `error`.
- `error`: error text if something failed.

Good context fields:

- `run_id`: connects a full workflow.
- `project_id`: connects messages for a product/project.
- `source_message_id`: points to the inbound message that caused this outbound message.
- `source_task_type`: explains why the follow-up exists.
- `provenance_source`: identifies the script, UI, or agent path that created the message.
- `provenance_agent`: identifies the agent responsible for creating the message.

## Artifacts and Outputs

Agents write completed work as markdown artifacts under `artifacts/`.

Examples:

- CEO strategy summary.
- PM roadmap.
- PM strategy routing plan.
- HR staffing review.
- Engineering feature implementation report.
- Marketing campaign brief.

The artifact system:

- Writes markdown files into agent-specific folders.
- Maintains an index file.
- Returns public-safe metadata through the router.
- Avoids exposing arbitrary local filesystem paths in the public artifact API.
- Lets the website show completed work even after messages have left active queues.

Important file:

- `enterprise_router/agent_artifacts.py`

## Live vs Mock Data

Live today:

- Router health.
- Agent registration data.
- Router queue data.
- Router audit events.
- Agent markdown artifacts.
- Manager interventions that submit real router messages.
- Onboarding trigger that can submit a real CEO reasoning message.
- Agent queue pages for currently queued work.
- Observability panels derived from audit and router lifecycle data.

Mock or demo today:

- Some revenue forecast visualizations.
- Some budget allocation visualizations.
- Sales pipeline metrics.
- Capacity/load percentages.
- Workflow progress cards.
- Many KPI cards.

Reason:

The router knows message lifecycle information. It does not automatically know real revenue, ROI, staffing utilization, or sales pipeline metrics unless agents emit structured metric events or the backend adds metric-specific endpoints.

## Setup

These steps assume PowerShell on Windows from the repository root:

```powershell
# Navigate to the root of the cloned repository
cd "path/to/teslastementerprise2026"
```

### Python Environment

Create and activate a virtual environment if one is not already available:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

If PowerShell blocks script activation, use your team's approved execution policy workflow or activate through another shell. Do not commit virtual environment folders.

### Website Dependencies

```powershell
cd website
npm install
```

Return to repo root when done:

```powershell
cd ..
```

## Running the System Locally

The normal local flow is:

1. Start the router.
2. Register agents and generate local env files.
3. Load worker env variables.
4. Start workers.
5. Start the website.
6. Seed or submit a workflow.

### 1. Start the Enterprise Router

From the repository root:

```powershell
$env:ENTERPRISE_ROUTER_BACKEND="sqlite"
$env:ENTERPRISE_ROUTER_DB="enterprise_router_demo.db"
$env:ENTERPRISE_ROUTER_ADMIN_SECRET="dev-admin-secret"
$env:ENTERPRISE_ROUTER_PORT="8000"
python -m enterprise_router.api
```

The router defaults to SQLite for local development.

### 2. Confirm Router Health

In a second terminal:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
```

Expected shape:

```json
{"status":"ok","backend":"sqlite"}
```

### 3. Register Agents and Generate Local Env Files

```powershell
$env:ENTERPRISE_ROUTER_URL="http://localhost:8000"
$env:ENTERPRISE_ROUTER_ADMIN_SECRET="dev-admin-secret"
python .\scripts\setup_local_runtime.py --write-website-env
```

This registers the default agents and writes local-only helper files:

- `.router_keys.ps1`
- `.router_keys.cmd`
- `website/.env.local`
- `website/.env.local.generated`

Do not commit those files. They contain local runtime secrets.

### 4. Load Worker Keys

PowerShell:

```powershell
. .\.router_keys.ps1
```

Command Prompt:

```cmd
call .router_keys.cmd
```

### 5. Start Agent Workers

```powershell
python .\run_agents.py --agents all
```

Expected behavior:

- CEO starts if `CEO_AGENT_API_KEY` is loaded.
- PM starts if `PM_AGENT_API_KEY` is loaded.
- Marketing starts if `MARKETING_AGENT_API_KEY` is loaded.
- HR starts if `HR_AGENT_API_KEY` is loaded.
- Strategic Advisor starts if `ADVISOR_AGENT_API_KEY` is loaded.
- Engineering starts in full mode if CrewAI dependencies are installed.
- Engineering starts in light-demo mode if CrewAI packages are missing.
- Sales is skipped because no runtime worker exists.
- Finance is skipped because no runtime worker exists.

To check availability without starting workers:

```powershell
python .\run_agents.py --agents all --list
```

To start a subset:

```powershell
python .\run_agents.py --agents CEO,PM,Engineering
```

### 6. Start the Website

In another terminal:

```powershell
cd website
npm run dev
```

Open the URL printed by Next.js, usually:

```text
http://localhost:3000
```

### 7. Seed a Workflow

From the repo root with worker keys loaded:

```powershell
python .\scripts\initiate_router_workflow.py
```

Optional variants:

```powershell
python .\scripts\initiate_router_workflow.py --no-include-engineering
python .\scripts\initiate_router_workflow.py --no-include-hr
python .\scripts\initiate_router_workflow.py --no-include-advisor
python .\scripts\initiate_router_workflow.py --dry-run
```

The seed script submits CEO-originated starter messages for a router-driven workflow.

## Website Commands

From `website/`:

```powershell
npm run dev
```

Runs the local development server.

```powershell
npm run build
```

Builds the production Next.js app.

```powershell
npm run start
```

Starts the built production app.

```powershell
npm run lint
```

Runs Next.js linting.

Important website env values:

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_ADMIN_SECRET`
- `NEXT_PUBLIC_MANAGER_API_KEY`
- `NEXT_PUBLIC_CEO_API_KEY`
- `NEXT_PUBLIC_PM_API_KEY`
- `NEXT_PUBLIC_MARKETING_API_KEY`
- `NEXT_PUBLIC_HR_API_KEY`
- `NEXT_PUBLIC_ENGINEERING_API_KEY`
- `NEXT_PUBLIC_ADVISOR_API_KEY`
- `NEXT_PUBLIC_SALES_API_KEY`
- `NEXT_PUBLIC_FINANCE_API_KEY`

These are generated by `scripts/setup_local_runtime.py --write-website-env`.

## Testing

Run the full Python test suite from the repo root:

```powershell
python -m pytest
```

Run a specific test file:

```powershell
python -m pytest tests\test_enterprise_router.py
```

Run a specific test:

```powershell
python -m pytest tests\test_enterprise_router.py::test_manager_intervention_requires_manager_role
```

The test suite covers:

- Message schema validation.
- Message bus behavior.
- Router client behavior.
- Router API behavior.
- Router storage behavior.
- Router end-to-end flows.
- CEO/router integration.
- HR/router integration.
- Engineering light-demo behavior.
- CLI entry points.
- Artifact APIs.
- Thread-safe agent behavior.
- Distribution token behavior.

`pytest.ini` sets the repo root on `pythonpath` and points pytest at `tests/`.

## Docker and Local LLM Notes

Several agents are designed to use local LLM tooling, especially CEO and Engineering.

CEO uses local Ollama endpoints:

- `http://localhost:11434/api/chat`
- `http://localhost:11434/api/generate`

Default CEO model:

- `mistral`

Engineering uses an Ollama-compatible model through CrewAI when running in full mode.

Default Engineering model env:

- `OLLAMA_MODEL`

Engineering default model value in code:

- `ollama/deepseek-coder-v2:16b`

If using Docker for Ollama, start Docker Desktop first, then start the Ollama container according to your local environment. A common local command used by this project is:

```powershell
docker start ollama-enterprise
```

This README intentionally avoids including private container configuration, private model paths, or real credentials.

If Ollama is not running:

- CEO model calls return a strategic-link error string rather than crashing the whole worker.
- Engineering full mode may not work, depending on CrewAI/Ollama configuration.
- Engineering light-demo mode can still process router messages and produce artifacts without generating code.

## Environment Variables

### Router Runtime

`ENTERPRISE_ROUTER_BACKEND`

Router storage backend. Use `sqlite` for normal local development. `mongo` is optional.

`ENTERPRISE_ROUTER_DB`

SQLite DB path for router persistence.

`ENTERPRISE_ROUTER_ADMIN_SECRET`

Admin secret for protected router admin endpoints.

`ENTERPRISE_ROUTER_SHARED_SECRET`

Registration request shared secret.

`ENTERPRISE_ROUTER_HOST`

Router API host. Default is `127.0.0.1`.

`ENTERPRISE_ROUTER_PORT`

Router API port. Code default is `8765`, but local demo commands often use `8000`.

`ENTERPRISE_ROUTER_URL`

Base URL used by agents and scripts, for example `http://localhost:8000`.

`ENTERPRISE_ROUTER_API_URL`

Compatibility alias for router base URL.

`ENTERPRISE_ROUTER_TIMEOUT_S`

HTTP timeout in seconds for `EnterpriseRouterClient`.

### Agent Identity and Keys

`ENTERPRISE_AGENT_NAME`

Default authenticated agent name for a process.

`ENTERPRISE_AGENT_API_KEY`

Default API key for a process.

Agent-specific keys:

- `CEO_AGENT_API_KEY`
- `PM_AGENT_API_KEY`
- `MARKETING_AGENT_API_KEY`
- `HR_AGENT_API_KEY`
- `ENGINEERING_AGENT_API_KEY`
- `ADVISOR_AGENT_API_KEY`
- `SALES_AGENT_API_KEY`
- `FINANCE_AGENT_API_KEY`
- `MANAGER_AGENT_API_KEY`

Compatibility aliases used in some places:

- `ENTERPRISE_ROUTER_AGENT_NAME`
- `ENTERPRISE_ROUTER_AGENT_API_KEY`
- `NEXT_PUBLIC_CEO_API_KEY`
- `NEXT_PUBLIC_PM_API_KEY`
- `NEXT_PUBLIC_PRODUCT_API_KEY`
- `NEXT_PUBLIC_MARKETING_API_KEY`
- `NEXT_PUBLIC_HR_API_KEY`
- `NEXT_PUBLIC_ENGINEERING_API_KEY`
- `NEXT_PUBLIC_ADVISOR_API_KEY`

### Website

`NEXT_PUBLIC_API_URL`

Router URL for the browser app.

`NEXT_PUBLIC_ADMIN_SECRET`

Admin secret used by local dashboard calls. Treat as local-only.

`NEXT_PUBLIC_MANAGER_API_KEY`

Manager identity key used for dashboard interventions.

Other `NEXT_PUBLIC_*_API_KEY` values let the website inspect agent queues where appropriate.

### Storage

`ENTERPRISE_BACKLOG_DB`

SQLite path for local `AgentBacklog`.

`ENTERPRISE_MESSAGE_BUS_JSONL`

JSONL path for local message-bus audit output.

`ENTERPRISE_ARTIFACTS_DIR`

Directory for markdown artifacts. Default is `<repo>/artifacts`.

`MONGODB_URI`

MongoDB connection string used by optional Mongo paths.

`ENTERPRISE_ROUTER_MONGO_DB`

Mongo database name for router Mongo backend.

`ENTERPRISE_MONGO_INTER_AGENT_DB`

Legacy/optional inter-agent Mongo database name.

### Engineering

`ENGINEERING_LIGHT_DEMO`

Forces Engineering light-demo mode.

`ENGINEERING_OFFLINE_DEMO_MONGO`

Uses legacy Mongo polling path for Engineering. Normal runtime should use the router instead.

`OUTPUT_DIR`

Where Engineering full mode writes generated projects.

`GITHUB_REPO_URL`

Optional remote for generated Engineering output.

`MAX_ITERATIONS`

Maximum Engineering review/fix iterations.

`OLLAMA_MODEL`

Engineering model name for local Ollama/CrewAI mode.

`POLL_INTERVAL_SECONDS`

Polling interval for some workers.

### Demo and Compatibility

`ENTERPRISE_ROUTER_OFFLINE_DEMO`

When set to `1`, allows explicit local `MessageBus` fallback for tests or demos. Do not use this for normal runtime.

`PM_STORAGE_BACKEND`

PM/Marketing storage backend. Leave unset for local file storage unless Mongo is intentionally needed.

## Storage Backends

### SQLite

SQLite is the default and recommended local router backend.

Advantages:

- Easy local setup.
- No external database required.
- Good for demos and tests.
- Stores router agents, queue records, leases, and audit events.

### MongoDB

MongoDB is optional.

Use Mongo only when:

- You intentionally want router persistence in Mongo.
- You have a configured local or remote MongoDB instance.
- You have set environment variables securely.

Do not hardcode credentials in source files.

### Local Files

Local files are used for:

- PM storage defaults.
- Markdown artifacts.
- Generated key helper files.
- Optional message-bus JSONL logs.

Local generated secret files should stay out of Git.

## Common Workflows

### Start Everything for a Demo

Terminal 1:

```powershell
$env:ENTERPRISE_ROUTER_BACKEND="sqlite"
$env:ENTERPRISE_ROUTER_DB="enterprise_router_demo.db"
$env:ENTERPRISE_ROUTER_ADMIN_SECRET="dev-admin-secret"
$env:ENTERPRISE_ROUTER_PORT="8000"
python -m enterprise_router.api
```

Terminal 2:

```powershell
$env:ENTERPRISE_ROUTER_URL="http://localhost:8000"
$env:ENTERPRISE_ROUTER_ADMIN_SECRET="dev-admin-secret"
python .\scripts\setup_local_runtime.py --write-website-env
. .\.router_keys.ps1
python .\run_agents.py --agents all
```

Terminal 3:

```powershell
cd website
npm run dev
```

Terminal 4:

```powershell
. .\.router_keys.ps1
python .\scripts\initiate_router_workflow.py
```

### Inspect Audit Events

```powershell
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/audit?limit=50" -Headers @{ "X-Admin-Secret" = "dev-admin-secret" }
```

### Inspect Router Health

```powershell
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/health"
```

### Inspect Worker Availability

```powershell
python .\run_agents.py --agents all --list
```

### Submit a Dry-Run Seed Preview

```powershell
python .\scripts\initiate_router_workflow.py --dry-run
```

## Troubleshooting

### `403 Invalid API key`

Likely cause:

- The router was restarted or agents were re-registered, but the worker or website still has stale keys.

Fix:

```powershell
python .\scripts\setup_local_runtime.py --write-website-env
. .\.router_keys.ps1
```

Then restart affected workers and restart `npm run dev`.

### `403 Task type ... is not allowed`

Likely cause:

- The agent registration allowlist is stale or missing that task type.

Fix:

```powershell
python .\scripts\setup_local_runtime.py --write-website-env
```

Restart workers afterward.

### Port conflict on `8000`

Likely cause:

- Another router or service is already running on port 8000.

Fix:

- Stop the existing process, or choose another port.
- If you change the router port, update `ENTERPRISE_ROUTER_URL` and `NEXT_PUBLIC_API_URL`.

### Website still uses old keys

Likely cause:

- Next.js reads env values at server startup.

Fix:

- Stop and restart `npm run dev`.

### PM or Marketing tries to connect to MongoDB

Likely cause:

- `PM_STORAGE_BACKEND=mongo` is set.

Fix:

- Unset `PM_STORAGE_BACKEND` for local file storage, or intentionally start/configure MongoDB.

### Engineering starts in light-demo mode

Likely cause:

- `crewai` or `crewai_tools` is not installed.

Fix:

- Install full Engineering dependencies if full code generation is needed.
- Otherwise, light-demo mode is acceptable for router and artifact demos.

### Queue page looks empty after submitting work

Likely cause:

- A worker fetched and acked/nacked the message quickly.

Fix:

- Check `/observability` for audit events.
- Check artifacts for completed output.

## Security and Privacy Notes

Do not commit:

- `.router_keys.ps1`
- `.router_keys.cmd`
- `website/.env.local`
- Real API keys.
- Real admin secrets.
- Real MongoDB credentials.
- Private model credentials.
- Generated files that contain sensitive customer or company information.

This README uses local development placeholders only.

Operational safety practices:

- Use the router instead of direct database writes for runtime communication.
- Keep local demo secrets local.
- Rotate generated keys if they are accidentally exposed.
- Prefer SQLite for local demos unless Mongo is specifically required.
- Avoid putting secrets in screenshots, artifacts, logs, or chat transcripts.
- Treat artifact markdown as user-visible output.

The artifact API is designed to return public-safe metadata and content rather than arbitrary filesystem access.

## Developer Notes

### Adding a New Agent

To add a new runtime agent:

1. Create the agent worker module.
2. Give it a canonical router name.
3. Register the agent in `scripts/bootstrap_router_agents.py`.
4. Add its API key env mapping.
5. Add it to `run_agents.py`.
6. Add a `run_single_agent.py` branch if needed.
7. Use `Message.create(...)` and `agent_transport.submit(...)` for outbound messages.
8. Fetch one message at a time.
9. Ack on success and nack on failure.
10. Add tests near the changed behavior.
11. Update this README.

### Adding a New Task Type

To add a task type:

1. Add the handler to the recipient agent.
2. Add the task type to that recipient's router allowlist.
3. Ensure the sender uses the standard message envelope.
4. Add correlation context such as `run_id` and `source_message_id`.
5. Add or update tests.
6. Re-run setup against the active router so the allowlist is refreshed.

### Runtime Rule of Thumb

Use:

- `EnterpriseRouterClient` for direct router client operations.
- `agent_transport` for shared agent send/fetch/ack/nack helpers.
- `Message.create(...)` for new envelopes.
- Router audit and artifacts for completed-work visibility.

Avoid:

- Directly writing another agent's queue.
- Treating local backlog as the shared source of truth.
- Adding new runtime paths that bypass the router.
- Committing generated secret files.

## Graphify Architecture Notes

The `graphify-out` report identified several core hubs and communities. The most connected concepts were:

- `Message`
- `EnterpriseRouterClient`
- `AgentRecord`
- `RegistrationRequest`
- `CeoAgent`
- `EnterpriseRouter`
- `AgentApiKeyRecord`
- `AgentBacklog`
- `MessageBus`
- `SQLiteStorage`

This matches the practical architecture:

- `Message` is central because every agent and transport path needs a shared envelope.
- `EnterpriseRouterClient` is central because agents, tests, and compatibility helpers use it to reach the router.
- `EnterpriseRouter` is central because it owns queueing, auth, access control, and audit.
- `AgentRecord` and `AgentApiKeyRecord` are central because the router must know who an agent is and whether it is allowed to act.
- `SQLiteStorage` is central because it is the default local persistence backend.
- `AgentBacklog` remains connected because agents still record local execution history, even though the router is the live queue of record.

Graphify also grouped the repository into communities such as:

- Enterprise Router API.
- Router Client.
- Agent Transport.
- CEO Agent Core.
- PM Agent Tools.
- Engineering Agent.
- HR Agent.
- Marketing Agent.
- Website API Client.
- Live Metrics.
- Run Agents CLI.
- Router Storage.
- Message Schema.
- Router E2E Tests.

Those communities informed this README structure. The documentation intentionally follows the same shape: router first, message contract second, agents third, website integration fourth, and setup/testing after the architecture is clear.

