# Global Requirements

## Decision-Making Hierarchy: 
CEO Agent is the central decision-maker. It delegates tasks, resolves conflicts, approves major actions (e.g., budgets >$10K, product launches), and monitors progress via periodic reports from all agents.

# Agent Specific Info

## CEO Agent
- **Role**: Strategic leader; sets goals, delegates, arbitrates.
- **Responsibilities**: Analyze market trends; define quarterly OKRs; assign tasks (e.g., "Launch MVP"); review reports; veto/approve proposals.
- **Inputs**: Market data, agent reports. Outputs: Task delegations, OKRs, final decisions.
- **Behaviors**: Uses reasoning chains for prioritization; prompts like "Prioritize based on ROI >20%." Tools: Analytics dashboard, email notifier.
- **Distribution tokens:** The CEO also governs [distribution tokens](#distribution-tokens-ceo-managed) (scenarios, minting, and per-agent assignments) when the message bus enforces token-gated sends.

## HR Agent
- **Role**: Manages talent and operations.
- **Responsibilities**: Recruit "virtual hires" (spawn sub-agents); onboard/train; performance reviews; compliance checks.
- **Inputs**: Role reqs from CEO. Outputs: Hiring plans, team rosters, training modules.
- **Behaviors**: Screens resumes; simulates interviews. Tools: LinkedIn scraper, calendar scheduler.

## Shared Router Integration

This repo now includes `enterprise_router_client.py`, a small adapter for the local `enterprise_router` FastAPI service. Runtime agent-to-agent communication must use this router instead of writing directly to MongoDB, sharing a SQLite file, or using the local `MessageBus`.

Recommended flow:

1. Start the Enterprise Router API.
2. Configure the router with SQLite for local development or MongoDB as the router storage backend.
3. Register each agent in the router and issue that agent an API key.
4. Set that key in this repo's environment.
5. Agents call the router API to send, fetch, ack, and nack messages.

Required environment variables for an agent process:

| Variable | Purpose | Default |
|----------|---------|---------|
| `ENTERPRISE_ROUTER_URL` | Base URL for the router API | empty |
| `ENTERPRISE_AGENT_NAME` | Default authenticated agent name for one process | empty |
| `ENTERPRISE_AGENT_API_KEY` | API key for one authenticated agent process | empty |
| `CEO_AGENT_API_KEY` | CEO worker API key used by `run_agents.py` | empty |
| `PM_AGENT_API_KEY` | PM worker API key used by `run_agents.py` | empty |
| `MARKETING_AGENT_API_KEY` | Marketing worker API key used by `run_agents.py` | empty |
| `HR_AGENT_API_KEY` | HR worker API key used by `run_agents.py` | empty |
| `ENGINEERING_AGENT_API_KEY` | Engineering worker API key used by `run_agents.py` | empty |
| `ADVISOR_AGENT_API_KEY` | Strategic Advisor worker API key used by `run_agents.py` | empty |
| `ENTERPRISE_ROUTER_TIMEOUT_S` | HTTP timeout in seconds | `10` |

`ENTERPRISE_ROUTER_API_URL`, `ENTERPRISE_ROUTER_AGENT_NAME`, and `ENTERPRISE_ROUTER_AGENT_API_KEY` are accepted as compatibility aliases, but new runtime setup should use the baseline names above. `ENTERPRISE_ROUTER_OFFLINE_DEMO=1` is the only supported way to intentionally use local `MessageBus`/legacy Mongo demo paths.

The HR worker in `hr-agents/hr_agent.py` now polls `POST /messages/fetch-next` through `EnterpriseRouterClient`, processes the envelope, then calls `ack` or `nack` on the shared router. The CEO and Advisor agents have the same router path through `process_one_router_message()`, and PM/Marketing/Engineering use `agent_transport` for send/fetch/ack. `AgentBacklog` remains useful as a local execution log, but the shared queue of record is the router API. The website visualizes the same queues and audit events through FastAPI without reading this repo's local files.

For future agents, reuse the same pattern:

```python
from enterprise_router_client import EnterpriseRouterClient

client = EnterpriseRouterClient.from_env(agent_name="Sales")
envelope = client.fetch_next("Sales")
if envelope:
    # process work here
    client.ack_message(envelope["id"], "Sales")
```

### Local Website Demo

Use this flow to run the router, all implemented agent workers, and the website locally. Replace `<project-root>` with the path to this repository. If the router is in a separate checkout, replace `<router-repo>` with that checkout path. Do not commit `.env.local` or real API keys.

The implemented runtime workers are `CEO`, `PM`, `Marketing`, `HR`, `Engineering`, and `Strategic Advisor`. `Sales` and `Finance` are registered with the router/website, but this codebase does not currently include worker implementations for them, so `run_agents.py` reports them as missing and skips them.

#### Prerequisites

- Python dependencies installed for this repo.
- Node dependencies installed for `website`.
- Ollama installed for the CEO's local LLM calls.
- The `mistral` Ollama model pulled locally.
- Optional for full Engineering mode: `crewai` and `crewai_tools`. If they are missing, Engineering starts in deterministic light-demo mode.

Install Python dependencies needed by the Engineering full mode:

```powershell
cd "<project-root>"
python -m pip install crewai crewai_tools
```

Install Ollama from `https://ollama.com/download`, then close and reopen your terminal so `ollama` is on PATH.

1. Start Ollama in its own terminal:

```powershell
ollama serve
```

In another terminal, pull the CEO model and verify Ollama is reachable:

```powershell
ollama pull mistral
Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/tags
```

If `ollama` is not recognized, Ollama is not installed or your terminal has not picked up the updated PATH.

2. Start the Enterprise Router API in a separate terminal:

```powershell
cd "<router-repo>"
$env:ENTERPRISE_ROUTER_BACKEND="sqlite"
$env:ENTERPRISE_ROUTER_DB="enterprise_router_demo.db"
$env:ENTERPRISE_ROUTER_ADMIN_SECRET="dev-admin-secret"
$env:ENTERPRISE_ROUTER_PORT="8000"
python -m enterprise_router.api
```

3. Confirm the router is reachable:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
```

A healthy local router returns JSON similar to:

```json
{"status":"ok","backend":"sqlite"}
```

4. Register the default agents and write local key files:

```powershell
cd "<project-root>"
$env:ENTERPRISE_ROUTER_URL="http://localhost:8000"
$env:ENTERPRISE_ROUTER_ADMIN_SECRET="dev-admin-secret"
python .\scripts\setup_local_runtime.py --write-website-env
```

This writes local-only secret files:

- `.router_keys.ps1`: PowerShell environment variables for agent workers.
- `.router_keys.cmd`: Command Prompt environment variables for agent workers.
- `website/.env.local`: Next.js environment variables for the website.
- `website/.env.local.generated`: generated website env backup.

These files are ignored by Git and should not be committed.

5. Load the generated worker keys:

```powershell
cd "<project-root>"
. .\.router_keys.ps1
```

Command Prompt alternative:

```cmd
cd "<project-root>"
call .router_keys.cmd
```

6. Check which workers can start:

```powershell
python .\run_agents.py --agents all --list
```

7. Start the implemented agent workers:

```powershell
python .\run_agents.py --agents all
```

Current local worker behavior:

- `CEO`, `PM`, `Marketing`, `HR`, and `Strategic Advisor` should start.
- `Engineering` runs the full CrewAI path when `crewai` and `crewai_tools` are installed.
- If those packages are missing, `Engineering` starts in deterministic light-demo mode. It still consumes `IMPLEMENT_FEATURE`, writes an Engineering artifact, submits `FEATURE_RESPONSE`, and acks the router message, but it does not generate code.
- `Sales` and `Finance` are skipped because this codebase does not yet include worker implementations for them.
- PM and Marketing use local file storage by default (`data/pm_storage.json`) so local MongoDB is not required. Set `PM_STORAGE_BACKEND=mongo` only if you intentionally want PM/Marketing domain storage in Mongo.

8. Start the website in another terminal:

```powershell
cd "<project-root>\website"
npm install
npm run dev
```

Open the Next.js URL from the terminal, usually `http://localhost:3000`.

9. Start the demo workflow from the website:

- If onboarding appears, complete it. The final onboarding step queues a real `CEO_REASONING_LOOP` message through the Enterprise Router.
- If the app opens directly to `/dashboard`, use `/chat` or an agent page to send an instruction to CEO. CEO-targeted website instructions use `CEO_REASONING_LOOP`.

Alternative command-line seed:

```powershell
python .\scripts\initiate_router_workflow.py
```

This queues starter messages as CEO. Without onboarding/chat/this seed, workers mostly poll empty queues.

10. Verify that the live demo is working:

```powershell
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/audit?limit=50" -Headers @{ "X-Admin-Secret" = "dev-admin-secret" }
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/artifacts?limit=10" -Headers @{ "X-Admin-Secret" = "dev-admin-secret" }
```

In the website, check:

- `/dashboard`: `Latest agent output` should show a live markdown artifact.
- `/observability`: audit count and throughput should update.
- `/agents/ceo`: CEO output should contain a real strategic decision when Ollama is running.
- `/agents/product`, `/agents/hr`, `/agents/engineering`: outputs appear after those workers process routed messages.

What you should see:

- `/dashboard` and `/observability` read router health, audit, and queue data.
- `/dashboard` shows the newest live agent artifact in the `Latest agent output` panel.
- `/observability` shows live audit events and router throughput after onboarding or the initiation script submits messages.
- `/messages` shows the live MANAGER queue. It does not show all historical messages.
- Agent pages show that agent's current inbound queue while messages are still queued, plus that agent's newest markdown output.
- Running workers fetch queued messages, process them, then ack or nack them.
- Router audit history shows the lifecycle of submitted, fetched, acked, and nacked messages.

### Seeing Agent Responses

Agent responses are not chat bubbles yet. They are router messages, audit events, and markdown artifacts.

Where to look:

```powershell
# Router audit log
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/audit?limit=50" -Headers @{ "X-Admin-Secret" = "dev-admin-secret" }
```

In the website:

- `/dashboard`: newest live artifact across all agents.
- `/observability`: best place to see that messages were submitted, fetched, acked, or nacked.
- `/messages`: shows the MANAGER queue only.
- `/agents/<agent>`: shows that agent's live inbound queue if the message has not already been fetched, and that agent's newest artifact under `Agent Outputs`.

Important: once a worker fetches and ack/nacks a message, it leaves the queue. Use audit and artifacts to see completed work. The current website is not a full conversation transcript.

### What Is Live vs. Mock

Live today:

- Router health (`/health`).
- Router audit log (`/audit`).
- Queue views (`/queue/{recipient}`).
- Markdown artifacts (`/artifacts`) from CEO, PM, HR, and Engineering light/full demo paths.
- Router throughput charts derived from audit events.
- Manager interventions that submit real router messages.

Still mock/demo today:

- Revenue forecast.
- Budget allocation.
- Sales pipeline.
- Capacity/load percentages.
- Workflow progress cards.
- Most KPI cards.

Those business visualizations need agents to emit structured business metric events, or the router needs a new `/metrics` endpoint. Right now the router knows message lifecycle data; it does not automatically know revenue, budget, ROI, or staffing capacity.

### How Autonomy Works Right Now

Autonomy is currently message-driven and rule/handler-driven:

- The initiation script submits starter messages as `CEO`.
- The router stores messages, validates auth/allowlists, computes priority, leases work, and records audit events.
- Workers poll their own queue.
- Each worker decides what to do based on `task_type`.
- Some workers submit follow-up messages. Example: PM receives `DEFINE_Q2_ROADMAP`, creates backlog/project data, then sends `LAUNCH_CAMPAIGN` and `PM_REPORT` to Marketing.
- Marketing may send `BUDGET_APPROVAL` to CEO or `CAMPAIGN_LAUNCHED` to Sales.

The router does not decide business strategy. It routes and records messages. The agents decide their next actions inside their task handlers.

### Onboarding Page

Onboarding is now a real backend trigger. The final onboarding step sends a `CEO_REASONING_LOOP` message to the router with the company name, one-liner, ideal customer, 90-day goal, selected departments, and a run id.

The backend system still requires:

1. The router is running.
2. Local keys are generated.
3. Agent workers are running.
4. Onboarding, website chat, or `scripts/initiate_router_workflow.py` submits starter messages.

If you already skipped onboarding and the dashboard opens immediately, send a CEO instruction from `/chat` or run the initiation script.

Common local issues:

- `ollama is not recognized`: install Ollama from `https://ollama.com/download`, then restart the terminal.
- `Strategic Link Error` or `localhost:11434` connection refused in CEO artifacts: Ollama is not running. Start `ollama serve` and confirm `Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/tags` returns JSON.
- CEO output says the `mistral` model is missing: run `ollama pull mistral`.
- `403 Invalid API key`: the website or agent process is using a stale key. Re-run `scripts/setup_local_runtime.py --write-website-env`, reload `.router_keys.ps1` or `.router_keys.cmd`, and restart the affected process.
- `403 Task type 'MANAGER_INTERVENTION' is not allowed`: the agent was registered with an old allowlist. Re-run `scripts/setup_local_runtime.py --write-website-env` against the running router.
- `WinError 10048` on port `8000`: another router is already running on that port. Stop it or use a different `ENTERPRISE_ROUTER_PORT` and update `NEXT_PUBLIC_API_URL` / `ENTERPRISE_ROUTER_URL` to match.
- Website still shows old keys after editing `.env.local`: restart `npm run dev`; Next.js reads environment variables at server startup.
- PM/Marketing try to connect to `localhost:27017`: make sure `PM_STORAGE_BACKEND` is not set to `mongo`, or run MongoDB intentionally.

## Distribution tokens (CEO-managed)

Governed **scenarios** throttle how many times an agent can complete a **token-gated** message on the bus. Each scenario has a **`cost_per_send`**: one successful `MessageBus.send` that names that scenario in the envelope consumes that many tokens from the **sender's** balance.

### How a send picks a scenario

The bus reads (first match wins):

1. `context["distribution_scenario"]`
2. `context["prompt_scenario"]`

If neither is set, or the string is **not** a registered scenario, the send is **not** charged (normal delivery).

If enforcement is on and the scenario **is** registered, the sender must have enough balance or the send raises `DistributionTokenError` and is **not** persisted.

### Costs, per-agent caps, and total caps (how the code works)

| Concept | Meaning in code |
|--------|------------------|
| **Task / scenario** | A registered scenario id (string), e.g. `STANDARD_DELEGATION`. |
| **Token cost per send** | `cost_per_send` for that scenario (minimum **1**). Each gated send deducts this from the sender's balance for that scenario. |
| **Per-agent cap** | Not a separate limit: it is whatever balance the CEO **minted** or **transferred** to that agent for that scenario. More sends are allowed only if the CEO increases that balance. |
| **Total cap (system-wide for one scenario)** | The **sum of all tokens in existence** for that scenario: CEO **mints** into one or more holders; tokens are only destroyed by **consumption** on send. There is no second hidden pool - the minted amount is the supply ceiling until the CEO mints again. |

**Simplest "baseline" task:** one governed bus message (one delivery attempt) for scenario `STANDARD_DELEGATION` with default `cost_per_send = 1` costs **1 token** from the sender's balance for `STANDARD_DELEGATION`.

### Reference allotment (example policy)

The table below is a **project default you can implement** with `CeoDistributionTokenRegistry` + `CeoAgent.mint_distribution_tokens` / `assign_distribution_tokens`. Numbers are not hardcoded; they document the intended budget.

**Scenario: `STANDARD_DELEGATION`** - routine delegations and cross-agent routing that should stay cheap.

| Agent (holder) | Allotted tokens (starting balance) | Notes |
|----------------|-------------------------------------|--------|
| CEO | 30 | Executive broadcasts and top-level routing |
| PM | 25 | Roadmap and coordination |
| Engineering | 20 | Build / technical delegations |
| Marketing | 15 | Campaign and messaging handoffs |
| HR | 10 | Internal people workflows |
| Sales | 10 | Pipeline and customer-facing handoffs |
| Finance | 10 | Budget and approval threads |
| UI | 10 | Design handoffs |

- **`cost_per_send` for `STANDARD_DELEGATION`:** **1** token per gated send.
- **Total minted supply (cap) for this scenario:** **130** (= sum of the column above). That is the maximum number of token **units** that can ever be spent **if the CEO never mints again**; each send spends `cost_per_send` (so up to **130** successful gated sends at cost 1, distributed by who still has balance).
- **Per-agent cap:** each row's allotment is that agent's **maximum spend** for this scenario until the CEO mints more to them or transfers tokens.

**Scenario: `EXECUTIVE_BROADCAST`** (optional, higher impact) - fewer, more expensive sends.

| Agent | Allotted tokens |
|-------|-----------------|
| CEO | 12 |
| PM | 3 |

- **`cost_per_send`:** **3** (each gated send burns 3 tokens).
- **Total minted supply for this scenario:** **15** token-units -> at most **5** gated sends if only CEO sends (`15 / 3`), or a mix of sends as long as balances allow.

### Wiring (summary)

- Create `CeoDistributionTokenRegistry(executive_name="CEO")` and attach it to `CeoAgent`. Token-gated local `MessageBus` examples are offline/demo-only; runtime agent delivery still goes through the Enterprise Router.
- CEO: `register_distribution_scenario`, `mint_distribution_tokens` (total supply), `assign_distribution_tokens` (per-agent rows in the table).
- Agents: include `distribution_scenario` or `prompt_scenario` in `context` only when that send should count against the budget.

## Pseoudocode of CEO Flow

    PROCEDURE Execute_CEO_Reasoning_Loop(IncomingEvent)
    
        CurrentContext <- Retrieve_Agent_Memory()
        CompanyState <- Fetch_Dashboard_KPIs()
        
        PromptInput <- Combine_Data(IncomingEvent, CurrentContext, CompanyState)
        
        ReasoningResponse <- Prompt_LLM(PromptInput, "JSON_Format")
        
        ParsedPlan <- Extract_Plan(ReasoningResponse)
        
        Save_To_Memory(ParsedPlan.Thought)
        
        ActionResults <- Initialize_Empty_List()
        
        FOR EACH Action IN ParsedPlan.Actions DO
        
            SWITCH Action.Name DO
            
                CASE "DelegateTask":
                    Result <- Route_To_Agent(Action.Parameters.Department, Action.Parameters.Directive)
                    Append Result TO ActionResults
                    
                CASE "ReplanBudget":
                    Result <- Adjust_Financial_Parameters(Action.Parameters)
                    Append Result TO ActionResults
                    
                CASE "SummarizeCycle":
                    Result <- Generate_Executive_Report(Action.Parameters)
                    Append Result TO ActionResults
                    
                DEFAULT:
                    Result <- Log_Unknown_Action(Action.Name)
                    Append Result TO ActionResults
                    
            END SWITCH
            
        END FOR
        
        IF Requires_Further_Reasoning(ActionResults) IS TRUE THEN
            RETURN Execute_CEO_Reasoning_Loop(ActionResults)
        END IF
        
        Update_Dashboard_Status("Idle", ParsedPlan.Thought)
        
        FinalResponse <- Prompt_LLM_For_Response(ActionResults)
        
        Save_To_Memory(IncomingEvent, FinalResponse)
        
        RETURN FinalResponse

    END PROCEDURE

## Pseudocode of Advisor Agent (Feedback Loop)
    PROCEDURE Execute_Advisor_Verification(ProposedPlan)

    CompanyState <- Fetch_Dashboard_KPIs()
    StrategicGoals <- Retrieve_Core_Directives()
    
    RiskAssessment <- Calculate_Plan_Risk(ProposedPlan, CompanyState)
    
    PromptInput <- Combine_Data(ProposedPlan, CompanyState, StrategicGoals, RiskAssessment)
    
    AdvisorResponse <- Prompt_LLM(PromptInput, "JSON_Format")
    
    ParsedFeedback <- Extract_Feedback(AdvisorResponse)
    
    Save_To_Audit_Log(ProposedPlan, ParsedFeedback)
    
    IF ParsedFeedback.IsApproved EQUALS TRUE THEN
        RETURN Construct_Approval(ParsedFeedback.Notes)
    ELSE
        RETURN Construct_Rejection(ParsedFeedback.Critique, ParsedFeedback.SuggestedModifications)
    END IF

END PROCEDURE

## Simulation Test: Process & Goals

The `standard_scenario_test.py` script acts as our primary integration test for the entire multi-agent architecture. It simulates a high-stakes corporate initiative to verify that our internal agent economy, message routing, and persistence layers are working in harmony.

### Primary Goals of the Test
1. **Verify the Token Economy:** Ensure the `CeoDistributionTokenRegistry` correctly mints, allocates, and deducts tokens. The test verifies that the CEO can use standard tokens for individual delegations and successfully execute a higher-cost `EXECUTIVE_BROADCAST` token for the final decision.
2. **Test Asynchronous Routing:** Confirm that the Enterprise Router correctly routes direct messages from the CEO to specific departments, as well as peer-to-peer messages (e.g., HR and Marketing sending cost data directly to Finance without CEO intervention).
3. **Validate Schema Compliance:** Ensure every agent communicates using the strict JSON envelope schema without triggering formatting errors.
4. **Confirm Router Persistence:** Verify that every transaction is recorded by the Enterprise Router storage backend. SQLite is the local default; MongoDB is supported only behind the router as an optional queue/audit backend.

### The Execution Process
When the simulation is triggered, the following workflow occurs automatically:
1. **Central Bank Initialization:** The CEO mints a total supply of standard and broadcast tokens, transferring specific budgets to each department.
2. **The Catalyst:** The CEO broadcasts initial directives to PM, Engineering, HR, Marketing, Sales, and Finance to begin the project.
3. **Departmental Processing:** Agents process their directives. Sub-routines trigger HR and Marketing to send financial estimates to the Finance Agent.
4. **Aggregation:** Finance calculates a strict ROI based on those inputs and routes the forecast back to the CEO. 
5. **Executive Decision:** The CEO ingests the final data, verifies the minimum ROI threshold is met, and consumes an `EXECUTIVE_BROADCAST` token to announce the final "GO" decision.

---

## Running and Verifying in Git Bash

If you are using Git Bash (or any standard Linux/Mac terminal), you can run the simulation and verify the outputs entirely via the command line.

### Run All Simulations
Make sure your virtual environment is activated, then run the tests as Python modules using pytest:

`python -m pytest`

### Run Specific Simulation
For running a specific simulation, run the test as a Python module:

`python -m standard_scenario_test`

# Instructions and Necessities

## Necessities
- IDE with python (preferably **VS Code**)
- **Ollama** and **Mistral**
- **Docker**

## Instructions
What to do to start working and pick up exactly where you left off:

- Open **Docker Desktop** (make sure it turns green)
- Activate your env: `source .venv/Scripts/activate`
- Wake up the AI: `docker start ollama-enterprise`

What to do to end your work session

- Deactivate you env: `deactivate`

