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


## Distribution tokens (CEO-managed)

Governed **scenarios** throttle how many times an agent can complete a **token-gated** message on the bus. Each scenario has a **`cost_per_send`**: one successful `MessageBus.send` that names that scenario in the envelope consumes that many tokens from the **sender’s** balance.

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
| **Token cost per send** | `cost_per_send` for that scenario (minimum **1**). Each gated send deducts this from the sender’s balance for that scenario. |
| **Per-agent cap** | Not a separate limit: it is whatever balance the CEO **minted** or **transferred** to that agent for that scenario. More sends are allowed only if the CEO increases that balance. |
| **Total cap (system-wide for one scenario)** | The **sum of all tokens in existence** for that scenario: CEO **mints** into one or more holders; tokens are only destroyed by **consumption** on send. There is no second hidden pool—the minted amount is the supply ceiling until the CEO mints again. |

**Simplest “baseline” task:** one governed bus message (one delivery attempt) for scenario `STANDARD_DELEGATION` with default `cost_per_send = 1` costs **1 token** from the sender’s balance for `STANDARD_DELEGATION`.

### Reference allotment (example policy)

The table below is a **project default you can implement** with `CeoDistributionTokenRegistry` + `CeoAgent.mint_distribution_tokens` / `assign_distribution_tokens`. Numbers are not hardcoded; they document the intended budget.

**Scenario: `STANDARD_DELEGATION`** — routine delegations and cross-agent routing that should stay cheap.

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
- **Per-agent cap:** each row’s allotment is that agent’s **maximum spend** for this scenario until the CEO mints more to them or transfers tokens.

**Scenario: `EXECUTIVE_BROADCAST`** (optional, higher impact) — fewer, more expensive sends.

| Agent | Allotted tokens |
|-------|-----------------|
| CEO | 12 |
| PM | 3 |

- **`cost_per_send`:** **3** (each gated send burns 3 tokens).
- **Total minted supply for this scenario:** **15** token-units → at most **5** gated sends if only CEO sends (`15 / 3`), or a mix of sends as long as balances allow.

### Wiring (summary)

- Create `CeoDistributionTokenRegistry(executive_name="CEO")`, attach to `CeoAgent` and `MessageBus(..., distribution_tokens=reg, enforce_distribution_tokens=True)`.
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
2. **Test Asynchronous Routing:** Confirm that the `MessageBus` correctly routes direct messages from the CEO to specific departments, as well as peer-to-peer messages (e.g., HR and Marketing sending cost data directly to Finance without CEO intervention).
3. **Validate Schema Compliance:** Ensure every agent communicates using the strict JSON envelope schema without triggering formatting errors.
4. **Confirm Dual-Persistence:** Verify that every transaction is simultaneously recorded to the cloud (MongoDB Atlas) and local storage (SQLite / JSONL).

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
