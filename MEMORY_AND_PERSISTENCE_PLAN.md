# Memory, Persistence, and Future Implementation Plan

## 1. Current storage landscape

### Local storage

- SQLite databases are used for the sales and finance tool layers:
  - [sales-agents/sales_tools.py](sales-agents/sales_tools.py)
  - [finance-agents/finance_tools.py](finance-agents/finance_tools.py)
- The router uses SQLite by default for queue, audit, registration, and message persistence:
  - [enterprise_router/sqlite_storage.py](enterprise_router/sqlite_storage.py)
- Agent artifacts are written to the repo-local artifacts directory:
  - [enterprise_paths.py](enterprise_paths.py)
- The backlog and message-bus files are also stored locally:
  - [enterprise_backlog.db](enterprise_backlog.db)
  - [enterprise_message_bus.jsonl](enterprise_message_bus.jsonl)

### Cloud / remote storage

- MongoDB support exists and is wired into the router storage abstraction:
  - [enterprise_router/mongo_storage.py](enterprise_router/mongo_storage.py)
  - [enterprise_paths.py](enterprise_paths.py)
- The repository already contains environment-driven Mongo support and router storage selection logic.
- The website is router-backed and expects live router data rather than direct local DB reads.

## 2. Persistence between runtime sessions

### Does it persist between runtime?

- SQLite-backed sales and finance data persists between runs as long as the DB files remain on disk.
- Router queue and audit state also persist when using SQLite and the same DB path.
- Artifact markdown files persist on disk as part of the repository or configured artifacts directory.
- In-memory bus flows and transient runtime state do not persist across restarts unless they are written to disk or the router.

### In-queue memory vs prompts

- The router stores queued messages and leases them to workers, so message state is preserved while waiting in the queue.
- Prompts are not retained as a separate memory system in the current design; the agent uses conversation history in memory for the current process only.
- The sales and finance agents do not currently maintain a persistent long-term memory layer beyond whatever is written to SQLite or artifacts.

### Website memory persistence

- The website currently persists limited user-facing state through browser local storage, for example onboarding and last-run state in the onboarding flow.
- The website does not currently have a server-side authenticated user memory layer.
- The website reflects live router state through polling rather than persistent browser-side enterprise memory.

## 3. Unfinished or unused implementations

### Unfinished / incomplete areas

- No authenticated multi-user account system is implemented for the website.
- No durable browser-side enterprise memory layer exists beyond simple local-storage keys.
- No cloud-backed user workspace or artifact sync layer is implemented for the website.
- No downloadable report assembly workflow is implemented to combine sales, finance, and agent output into a single packaged artifact.
- No persistent long-term agent memory beyond SQLite and artifact files is implemented.

### Already present but not yet fully integrated

- MongoDB storage support is present but not yet the default operational path in the local runtime setup.
- The router has an artifact surface and audit endpoints that could be used to build richer persistence features.

## 4. Future implementation options for persistence and saving

### Option A: Browser cookies and local browser storage

#### What it would be

Use cookies or browser local storage to preserve small UI state, onboarding progress, recent workflow context, and selected preferences.

#### Pros

- Very easy to implement.
- No backend changes required for simple state.
- Works well for UI preferences and lightweight workflow continuity.

#### Cons

- Cookies are limited in size and are not appropriate for large structured state.
- Browser storage is not secure for sensitive data without encryption.
- Not suitable as the only source of truth for enterprise state.

#### Suggested implementation

- Store a small JSON blob in browser local storage for user preferences and recent session context.
- Use cookies only for non-sensitive session markers.
- Encrypt any sensitive fields before writing them.

---

### Option B: Sign up / sign in with authentication

#### What it would be

Add a real authentication layer for website users, with password hashing and salt-based storage.

#### Pros

- Allows user-specific memory and workspaces.
- Supports multi-tenant or multi-user workflows.
- Enables secure, persistent dashboards and saved artifacts.

#### Cons

- Requires careful security review.
- Needs password reset and session-management flows.
- Adds operational complexity.

#### Suggested implementation

- Use a library already present in the repo, such as cryptography or rsa, for encryption-related support.
- Use a salted password-hash flow such as PBKDF2, scrypt, or Argon2 if available.
- Store user records in a secure backend store such as SQLite for local dev or MongoDB for cloud.
- Use signed JWTs or server-managed sessions for login state.

> Note: The repository already includes cryptography and rsa in requirements, so these libraries are suitable for secure-key or encrypted payload work.

---

### Option C: Cloud storage via MongoDB

#### What it would be

Use the existing MongoDB infrastructure as the primary durable backend for router state, artifacts, and user memories.

#### Pros

- Strong fit with the existing router abstraction.
- Scales better than local SQLite for multi-user or cloud deployments.
- Good choice for shared artifacts, audit history, and persisted state.

#### Cons

- Requires a running MongoDB service.
- More operational overhead than local SQLite.
- Requires proper indexing, backup, and access control.

#### Suggested implementation

- Switch the router backend to MongoDB in cloud deployments.
- Store user workspaces, artifact metadata, and memory records in dedicated collections.
- Add indexes for agent, task type, run_id, and user_id.

---

### Option D: User OneDrive / Microsoft cloud storage

#### What it would be

Allow the system to sync generated reports and artifacts to the user’s OneDrive account.

#### Pros

- Familiar to end users.
- Good for downloadable reports and collaborative file sharing.
- Fits a “save my outputs to my cloud drive” story well.

#### Cons

- Requires Microsoft Graph / OAuth integration.
- Upload permission and app registration setup are required.
- More complex than local artifact writing.

#### Suggested implementation

- Add an optional export step that uploads artifacts to a user-authorized OneDrive folder.
- Use Microsoft Graph with delegated permissions and a refresh-token flow.
- Consider permission scopes carefully to avoid overreach.

---

### Option E: Downloadable PDF report assembly

#### What it would be

Create a single downloadable PDF that aggregates agent artifacts, summaries, financials, and workflow output.

#### Pros

- Gives users a polished deliverable.
- Great for final product handoff.
- Easier to share than many markdown files.

#### Cons

- Requires a report-generation pipeline.
- Rendering HTML to PDF can be inconsistent across browsers.
- Needs careful merging of content from many sources.

#### Suggested implementation

- Collect artifacts from the router artifact endpoint and the local SQLite stores.
- Build a unified report document with sections for strategy, roadmap, finance, sales, and audit.
- Render it as HTML first and then export to PDF.

## 5. Additional implementation ideas worth considering

### A. Workspace memory per user

Create a per-user workspace record that stores:
- agent conversation state
- last run IDs
- selected artifacts
- recent decisions
- saved reports

This would be the natural next step beyond simple browser memory.

### B. Event-sourced memory log

Store every significant agent action as an event in a structured log. This makes it easier to reconstruct state later and audit how decisions were made.

### C. Semantic artifact search

Index generated artifacts and reports so users can search them later by topic, run, or department.

### D. Export packages

Allow exporting a full workflow bundle as:
- ZIP archive
- PDF report
- Markdown package
- JSON snapshot

### E. Hybrid persistence model

Use a layered model:
- browser storage for quick UI continuity
- local SQLite for offline/dev persistence
- MongoDB or cloud storage for shared or long-lived state
- OneDrive export for user-facing file delivery

## 6. Recommended path forward

A practical roadmap would be:

1. Implement a lightweight user-authentication flow.
2. Add a persistent workspace record for each authenticated user.
3. Store session and artifact metadata in MongoDB or a cloud-friendly backend.
4. Add an export pipeline for PDF and ZIP delivery.
5. Optionally add OneDrive export as a later integration.
