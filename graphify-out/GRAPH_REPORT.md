# Graph Report - C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026  (2026-05-25)

## Corpus Check
- 102 files · ~156,180 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 906 nodes · 2365 edges · 61 communities detected
- Extraction: 51% EXTRACTED · 49% INFERRED · 0% AMBIGUOUS · INFERRED: 1155 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]

## God Nodes (most connected - your core abstractions)
1. `Message` - 133 edges
2. `get()` - 119 edges
3. `EnterpriseRouterClient` - 113 edges
4. `MessageBus` - 59 edges
5. `CeoAgent` - 56 edges
6. `EnterpriseRouter` - 54 edges
7. `ThreadSafeAgentMixin` - 53 edges
8. `AgentBacklog` - 46 edges
9. `SQLiteStorage` - 35 edges
10. `MongoStorage` - 32 edges

## Surprising Connections (you probably didn't know these)
- `SQLite-based storage for agent interactions and logs.     Strictly maps to the` --uses--> `Message`  [INFERRED]
  C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\agent_backlog.py → C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\message_schema.py
- `Creates the database tables if they don't exist yet.         - interactions: st` --uses--> `Message`  [INFERRED]
  C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\agent_backlog.py → C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\message_schema.py
- `Insert a message/task into the interactions table.         Accepts a :class:`~m` --uses--> `Message`  [INFERRED]
  C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\agent_backlog.py → C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\message_schema.py
- `Returns all interactions with status 'pending'.         Use this to find tasks` --uses--> `Message`  [INFERRED]
  C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\agent_backlog.py → C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\message_schema.py
- `Returns all interactions where the agent was either sender or recipient.` --uses--> `Message`  [INFERRED]
  C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\agent_backlog.py → C:\Users\pragy\Documents\High School Work\11th Grade\Intership Compilation Branch\teslastementerprise2026\message_schema.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (55): AckBody, AgentBody, ApprovalBody, FetchBody, ManagerInterventionBody, MessageBody, NackBody, RegistrationRequestBody (+47 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (94): Fetch, process, and ack/nack one Advisor message from the enterprise router., Advisor Agent Class     Responsible for auditing the CEO's decisions and ensuri, Advisor Agent Class     Responsible for auditing the CEO's decisions and ensuri, Takes a JSON message from the CEO, evaluates the payload against the          c, Takes a JSON message from the CEO, evaluates the payload against the          c, Shared enterprise-router transport for all department agents.  When ``ENTERPRI, Submit an envelope; returns message id., Fetch and ack all queued messages for an agent (router or local peek). (+86 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (61): AdvisorAgent, MessageBus, create(), envelope_dict(), from_dict(), normalize_envelope(), message_schema.py  Single source of truth for the enterprise agent message env, Return a dict for logging/serialization without strict validation. (+53 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (44): get(), post(), request(), main(), Register default department agents on a running enterprise router (admin API)., CeoAgent, auditToActorCounts(), auditToTaskTypeCounts() (+36 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (38): get_agent_logger(), log_inter_agent_message(), Specifically handles the standardized JSON schema for agent communication., Creates and returns a custom logger for an agent., handleKeyDown(), handleSelect(), submit(), _extract_json_array() (+30 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (31): utc_now(), getSlashSuggestions(), parseCommand(), handleChange(), handleSend(), uid(), commit_and_push(), EngineeringAgent (+23 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (35): AgentBacklog, Returns all interactions with status 'pending'.         Use this to find tasks, SQLite-based storage for agent interactions and logs.     Strictly maps to the, Returns all interactions where the agent was either sender or recipient., Update the status of an interaction.         e.g. from 'pending' to 'in_progres, Log an action an agent took.         Call this inside hireAgents() and fireAgen, Get logs. Pass a task_id to filter by task, or leave empty for all logs., Wipes the entire database and recreates it fresh.         Useful for testing — (+27 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (37): build_envelope(), hr_worker(), process_one_hr_message(), queue_mint_token_request(), Fetch one HR message from the shared enterprise_router queue and process it., Queue a sample CEO -> HR message through enterprise_router for demos., Poll enterprise_router for HR messages and process them., Ask the CEO agent to mint distribution tokens for a scenario and holder. (+29 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (42): ack(), client(), delegate(), drain_mailbox(), _env_flag_enabled(), _local_bus(), local_fallback_enabled(), make_envelope() (+34 more)

### Community 9 - "Community 9"
Cohesion: 0.1
Nodes (3): MongoStorage, _utc_now(), RouterStorage

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (1): ABC

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (17): agent_slug(), envelope_prompt_json(), _format_markdown(), poll_one_router_message(), poll_router_prompts_loop(), Persist agent deliverables as markdown and poll router prompt envelopes., Write a markdown artifact under ``artifacts/<agent-slug>/``.      Returns a re, Fetch one leased envelope, optionally log prompt JSON, run ``handler``, then ack (+9 more)

### Community 12 - "Community 12"
Cohesion: 0.27
Nodes (9): agentH(), asNullableString(), asNumber(), asRecord(), asString(), managerH(), normalizeDeliveryState(), normalizeMessageStatus() (+1 more)

### Community 13 - "Community 13"
Cohesion: 0.43
Nodes (7): AgentSpec, list_status(), main(), missing_modules(), Start every implemented Enterprise Router-backed agent worker.  Run this after, resolve_key(), split_agents()

### Community 14 - "Community 14"
Cohesion: 0.33
Nodes (2): import_legacy_ceo_agents_module(), Import ``ceo-agents/<module_name>.py`` as a synthetic package module so     its

### Community 15 - "Community 15"
Cohesion: 0.52
Nodes (6): useAgents(), useAudit(), useHealth(), usePolling(), useQueue(), useRegistrations()

### Community 16 - "Community 16"
Cohesion: 0.67
Nodes (0): 

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (0): 

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (0): 

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (0): 

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (0): 

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Factory for a new outbound envelope (UUID + ISO-8601 UTC timestamp).

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (0): 

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (0): 

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (0): 

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (0): 

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (0): 

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Returns the local path for the SQLite DB.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Returns the local path for the JSONL audit file.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Returns the secure MongoDB URI from the .env file.     Falls back to a local de

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Returns the specific database name.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Domain persistence for PM and Marketing agents.     Does not handle the enterpr

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Return required interface checks inferred from the task spec.         This prev

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Return source filenames that must exist for known feature types.

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Only true for pure Python class-based number guessing games, not Streamlit apps.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Prompt hint injected into generation prompts for files that have         strict

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Validate required class/method contract in generated source files.         Retu

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Dedicated test-generation prompt — produces more reliable test code than the

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Directly validate core runtime behavior for the number guessing benchmark.

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Validate basic Streamlit UI quality in generated main.py.

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Run a test file and return (passed: bool, detail: str).         Supports Python

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Legacy Mongo inbox for Engineering when the router is not configured.

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): # TODO: This class is a work in progress and not fully integrated yet.

## Knowledge Gaps
- **59 isolated node(s):** `Creates and returns a custom logger for an agent.`, `Specifically handles the standardized JSON schema for agent communication.`, `Single source of truth for enterprise persistence.  - **SQLite** — internal ba`, `Returns the local path for the SQLite DB.`, `Returns the local path for the JSONL audit file.` (+54 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 17`** (2 nodes): `page.tsx`, `Home()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (2 nodes): `page.tsx`, `handleSend()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (2 nodes): `page.tsx`, `copyJSON()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (2 nodes): `OnboardingGuard.tsx`, `OnboardingGuard()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (2 nodes): `ChatMessage.tsx`, `AgentAvatar()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Factory for a new outbound envelope (UUID + ISO-8601 UTC timestamp).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `multithreaded_agent.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `thread_safe_agent.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `next-env.d copy.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `next-env.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `next.config copy.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `next.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `postcss.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `tailwind.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `layout.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `WorkerAgentsDropdown.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `SlashMenu.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Sidebar.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `api-types.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `mock-data.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `types.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Returns the local path for the SQLite DB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Returns the local path for the JSONL audit file.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Returns the secure MongoDB URI from the .env file.     Falls back to a local de`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Returns the specific database name.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Domain persistence for PM and Marketing agents.     Does not handle the enterpr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Return required interface checks inferred from the task spec.         This prev`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Return source filenames that must exist for known feature types.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Only true for pure Python class-based number guessing games, not Streamlit apps.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Prompt hint injected into generation prompts for files that have         strict`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Validate required class/method contract in generated source files.         Retu`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Dedicated test-generation prompt — produces more reliable test code than the`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Directly validate core runtime behavior for the number guessing benchmark.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Validate basic Streamlit UI quality in generated main.py.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Run a test file and return (passed: bool, detail: str).         Supports Python`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Legacy Mongo inbox for Engineering when the router is not configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `# TODO: This class is a work in progress and not fully integrated yet.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `Community 3` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 11`, `Community 12`, `Community 13`, `Community 14`?**
  _High betweenness centrality (0.331) - this node is a cross-community bridge._
- **Why does `Message` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 8`, `Community 11`?**
  _High betweenness centrality (0.197) - this node is a cross-community bridge._
- **Why does `EnterpriseRouterClient` connect `Community 1` to `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 8`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Are the 130 inferred relationships involving `Message` (e.g. with `AgentBacklog` and `SQLite-based storage for agent interactions and logs.     Strictly maps to the`) actually correct?**
  _`Message` has 130 INFERRED edges - model-reasoned connections that need verification._
- **Are the 117 inferred relationships involving `get()` (e.g. with `log_inter_agent_message()` and `submit()`) actually correct?**
  _`get()` has 117 INFERRED edges - model-reasoned connections that need verification._
- **Are the 94 inferred relationships involving `EnterpriseRouterClient` (e.g. with `Shared enterprise-router transport for all department agents.  When ``ENTERPRI` and `Build and validate a canonical envelope dict.`) actually correct?**
  _`EnterpriseRouterClient` has 94 INFERRED edges - model-reasoned connections that need verification._
- **Are the 49 inferred relationships involving `MessageBus` (e.g. with `Shared enterprise-router transport for all department agents.  When ``ENTERPRI` and `Build and validate a canonical envelope dict.`) actually correct?**
  _`MessageBus` has 49 INFERRED edges - model-reasoned connections that need verification._