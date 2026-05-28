# company_brain_backend

# Company Brain for Finance - Architecture Document

## Vision

Company Brain is not a chatbot over company documents.  
It is an **operational memory and execution layer** for finance teams.

The product should model:
- people and ownership
- workflows and dependencies
- decisions and rationale
- systems and source-of-truth data
- operational context over time
- next-best actions

In one line:

> Build an AI operating memory for how finance actually runs inside a company.

---

## What Makes This Different

### Not enough
- "Ask AI about company docs"
- basic RAG with vector search
- static dashboards with no actions

### Required
- workflow intelligence
- decision memory
- relationship intelligence (graph)
- permission-safe retrieval
- execution agents that can act

---

## Finance Task Universe (What the System Must Handle)

The architecture must support the recurring finance responsibilities below.

### 1) Accounts Payable (AP)
- invoice intake and classification
- PO-invoice-GRN matching (3-way match)
- approval routing and escalations
- payment run preparation
- duplicate/invalid invoice detection
- vendor dispute handling

### 2) Accounts Receivable (AR)
- invoice generation and dispatch
- collections workflows and reminders
- dispute handling and root-cause tagging
- DSO tracking and risk scoring
- customer payment behavior analysis

### 3) General Ledger and Record-to-Report
- journal postings and validation
- accruals and reclassification entries
- close checklist orchestration
- intercompany reconciliation
- variance analysis across entities/cost centers

### 4) Cash and Treasury Operations
- daily cash position tracking
- bank reconciliation
- liquidity forecasting (short and medium horizon)
- debt covenant monitoring
- FX exposure tracking and hedging support

### 5) FP&A
- annual budgeting
- rolling forecasts
- scenario planning (best/base/worst case)
- board and leadership KPI packages
- budget vs actual explanations

### 6) Revenue Finance
- contract-to-revenue linkage
- revenue recognition checks
- deferred revenue schedules
- pricing and discount leakage analysis

### 7) Tax and Compliance
- GST/VAT/TDS workflows
- statutory filing preparation
- evidence and audit trail assembly
- policy compliance checks

### 8) Payroll Finance and Expense Controls
- payroll accrual validation
- reimbursements and expense policy checks
- anomaly detection in payroll/expenses

### 9) Internal Controls and Audit
- control testing workflows
- exception management and remediation tracking
- policy attestation reminders
- audit-readiness packs with citations

---

## Reference Architecture (Layered)

## 1. Data Ingestion Layer

Ingest from operational systems:
- ERP/accounting system
- banking feeds
- CRM (for revenue and collections context)
- contracts and documentation systems
- tickets/project tools
- collaboration tools (Slack/email for approvals and decisions)
- data warehouse and internal APIs

Requirements:
- connectors with mixed sync modes (webhooks, polling, CDC)
- incremental updates
- source reliability scoring
- replayable ingestion logs

---

## 2. Canonical Data Model Layer

Normalize data into common entities:
- Person
- Team
- Legal Entity
- Vendor
- Customer
- Contract
- Transaction
- Invoice
- Journal Entry
- Workflow
- Approval Step
- Decision
- Incident/Exception

Critical capability:
- multi-source identity resolution (for people, entities, vendors, customers)

---

## 3. Processing and Enrichment Layer

Convert raw data into intelligence:
- document chunking for long unstructured artifacts
- embeddings generation
- metadata extraction (owner, department, project, date, amount, priority, risk)
- event enrichment (detect blockers, delays, exceptions)
- classification of workflow state

---

## 4. Vector Retrieval Layer

Purpose:
- semantic retrieval over policies, SOPs, tickets, notes, contracts, and discussions

Initial stack recommendation:
- PostgreSQL + pgvector

Why:
- lower cost
- easier operations
- fewer moving parts in early stages

---

## 5. Knowledge Graph Layer (Strategic Differentiator)

Store relationships like:
- person -> owns -> workflow
- workflow -> blocked by -> exception
- exception -> linked to -> ticket/decision
- decision -> impacts -> customer segment or KPI
- contract -> affects -> revenue schedule

Suggested graph store:
- Neo4j (MVP and early growth)

Why this matters:
- enables causal reasoning and operational tracing
- goes beyond "similar text retrieval"

---

## 6. Memory Layer (Moat)

Memory types:
- short-term memory: current cycle status and blockers
- long-term memory: stable operating preferences and norms
- decision memory: what was decided, by whom, and why
- workflow memory: recurring failure modes and mitigation patterns

Examples:
- "Legal approval is always required before this vendor category is paid."
- "Customer segment X has high late-payment risk in quarter-end weeks."
- "Team Y prefers async review before close sign-off meetings."

---

## 7. Retrieval Orchestration Layer

Decides what context is sent to models and agents.

Must support:
- hybrid retrieval (semantic + keyword + metadata)
- graph traversal retrieval
- source trust prioritization
- permission-aware filtering
- context packaging with citations and confidence

This is one of the hardest engineering problems.

---

## 8. Agent Execution Layer

Domain agents for finance operations:
- AP exception handling agent
- Close orchestration agent
- AR collections intelligence agent
- Cash risk alert agent
- Policy and control compliance agent
- Audit evidence assembly agent

Agent actions:
- create tasks/tickets
- request approvals
- generate reconciliations and summaries
- detect and route bottlenecks
- trigger follow-up workflows

Orchestration approach:
- LangGraph (recommended for structured multi-step workflows)

---

## 9. LLM and Reasoning Layer

Multi-model strategy:
- GPT-4.1 / GPT-5 class models for broad quality
- Claude-class model for long-context reasoning
- optional cost-optimized models later for narrow subtasks

Principle:
- optimize for correctness and trust first, then optimize cost

---

## 10. Security, Permissions, and Governance Layer

Enterprise-critical requirements:
- RBAC + ABAC + source ACL propagation
- field/document-level access control
- encryption in transit and at rest
- immutable audit logs
- action guardrails and approval gates
- PII/payroll segmentation controls

Hard rule:
- if a user cannot access a source document, the AI cannot use it in response context.

---

## 11. Experience and Product Layer

The UI should not be only a chat screen.

Required product surfaces:
- operational dashboard (finance health + bottlenecks)
- workflow map (what is blocked and why)
- decision timeline (why actions happened)
- action center (pending approvals and tasks)
- source tracing panel (citations/confidence)
- role-specific views (CFO, controller, finance ops, AP/AR manager)

---

## Key Technical Challenges

### 1) Correct Context Retrieval
- not finding documents, but finding the right operational context
- requires hybrid + graph + memory-aware retrieval

### 2) Hallucination and Trust
- finance domain has low tolerance for incorrect outputs
- enforce citations, confidence scores, and verification workflows

### 3) Real-Time Sync and Drift
- financial state changes continuously
- need event-driven + incremental architecture

### 4) Identity Resolution
- same person/entity appears differently across systems
- unresolved identities break retrieval and automation quality

### 5) Action Safety
- autonomous actions need policy and approval guardrails
- high-risk operations should remain human-in-the-loop

---

## MVP Strategy (Finance-First)

Target ICP:
- finance-focused startups and SaaS companies (roughly 50-800 employees)

Do not build horizontal "AI for every team" first.

Start with one vertical and a few high-value workflows.

### Initial MVP Workflows
1. Month-end close acceleration
2. AP exception triage and routing
3. Cash forecast + collections risk alerts

### MVP Inputs
- ERP/accounting data
- bank statements/feeds
- collaboration approvals (Slack/email)
- documents (policies/contracts/SOPs)
- issue tracking context

### MVP Outputs
- prioritized action queue
- blocker alerts
- reconciliation and variance narratives
- audit-ready citations
- decision trails

---

## Suggested Initial Tech Stack

### Backend
- FastAPI (Python) or Node.js

### Orchestration
- LangGraph

### Storage
- PostgreSQL + pgvector
- Neo4j (graph)

### Queue / Jobs
- Redis + BullMQ (or equivalent queueing stack)

### Frontend
- Next.js

### Auth
- Clerk or Auth0

### Infra
- AWS

---

## 90-Day Delivery Plan

### Weeks 1-3: Data Foundation
- build connectors for ERP, bank feed, docs, approvals
- implement canonical finance data model
- implement identity resolution v1

Success metrics:
- high ingestion reliability
- low identity collision rate

### Weeks 4-6: Intelligence Foundation
- implement hybrid retrieval
- implement graph relations and traversal APIs
- implement memory schema (short-term + decision memory v1)

Success metrics:
- high relevance of top retrieved contexts
- high citation coverage in responses

### Weeks 7-9: Agent Workflows
- AP exception agent
- close checklist agent
- cash risk alerting agent

Success metrics:
- reduced manual finance triage
- faster issue resolution cycles

### Weeks 10-13: Trust and Pilot
- enforce RBAC/ABAC + source ACLs
- full audit logging and action controls
- pilot with one design partner

Success metrics:
- high trust score from finance users
- zero critical permission leaks

---

## Strategic Value

The long-term value is not "better chat."

The value is proprietary organizational intelligence about:
- how finance decisions happen
- where execution breaks
- which patterns predict risk
- which workflows are inefficient
- what actions reliably improve outcomes

This is the path from assistant -> system of intelligence -> system of execution.

---

## Implementation Status

Initial monorepo scaffold has been created with clean, lightly-coupled boundaries:

- `apps/api` -> FastAPI backend (domain modules and migration setup)
- `apps/web` -> Next.js frontend with separate `admin` and `workspace` routes
- `packages/contracts` -> shared TypeScript contracts and domain types
- `infra` -> Docker Compose for Postgres (pgvector), Redis, and Neo4j

Principles used:
- bounded-context modules
- shared contracts, no direct cross-app imports
- infra separated from application code
- tenant-aware schema baseline

Current delivery state:
- v1 API contracts implemented and wired in FastAPI
- PostgreSQL schema extended with workflows, decisions, memory, agent runs/actions, and audit logs
- queue event envelope and Redis publisher implemented
- admin and workspace dashboards connected to live API endpoints

---

## Concrete Implementation Spec

This section defines implementation-level structure for the first production version.

## 1) Service Boundaries

Use a modular monolith first (single deployable, clear module boundaries), then split to services as load/security needs grow.

### A. Identity and Access Service
- user auth integration (Clerk/Auth0)
- org, team, role, and policy mapping
- RBAC + ABAC evaluation
- source ACL propagation

### B. Connector and Ingestion Service
- connector adapters (ERP, bank, CRM, docs, Slack/email)
- scheduler + webhook handlers + CDC consumers
- ingest run tracking, retries, dead-letter handling
- normalized events emission

### C. Canonical Finance Model Service
- entity normalization and upserts
- identity resolution (person/vendor/customer/entity)
- cross-source linking and dedupe
- schema validation and quality checks

### D. Knowledge Processing Service
- chunking pipeline
- embedding pipeline
- metadata extraction pipeline
- source trust scoring

### E. Retrieval Service
- hybrid retrieval (keyword + vector + metadata)
- graph traversal retrieval
- context ranking and packing
- citation bundle generation

### F. Memory Service
- short-term operational memory store
- long-term decision/workflow memory store
- memory write policies (what gets remembered)
- memory decay/versioning rules

### G. Agent Orchestration Service
- workflow state machine (LangGraph)
- tool invocation routing
- action policy checks
- human-in-the-loop approvals

### H. Action and Integration Service
- create Jira/Linear tasks
- send Slack/email notifications
- write back status to ERP/ticketing where allowed
- idempotent action logs

### I. Audit and Observability Service
- immutable audit trail
- model input/output trace records
- latency/reliability metrics
- alerting and operational dashboards

### J. API Gateway / BFF Service
- auth-aware API surface for frontend
- request shaping for role-specific views
- rate limiting and tenant isolation

---

## 2) Database Schema (Postgres + pgvector + Neo4j)

## 2.1 PostgreSQL (Transactional + Metadata)

Core tables (initial):
- `organizations` (id, name, plan, created_at)
- `users` (id, org_id, email, display_name, status)
- `roles` (id, org_id, name)
- `user_roles` (user_id, role_id)
- `data_sources` (id, org_id, type, status, config_ref, last_sync_at)
- `ingestion_runs` (id, source_id, started_at, completed_at, status, error_summary)
- `identity_profiles` (id, org_id, canonical_type, canonical_key, confidence)
- `identity_aliases` (id, identity_profile_id, source, source_key, raw_value)
- `finance_entities` (id, org_id, entity_type, name, external_ref)
- `vendors` (id, org_id, finance_entity_id, payment_terms, risk_tier)
- `customers` (id, org_id, finance_entity_id, segment, risk_tier)
- `invoices` (id, org_id, invoice_type, vendor_id, customer_id, amount, currency, due_date, status)
- `journal_entries` (id, org_id, period, entry_date, account_code, debit, credit, status)
- `approvals` (id, org_id, object_type, object_id, step_no, approver_user_id, status, decided_at)
- `workflows` (id, org_id, workflow_type, state, owner_user_id, started_at, closed_at)
- `workflow_steps` (id, workflow_id, step_type, state, started_at, ended_at)
- `decisions` (id, org_id, decision_type, title, rationale, made_by, decided_at)
- `incidents` (id, org_id, incident_type, severity, status, detected_at, resolved_at)
- `memory_records` (id, org_id, memory_type, subject_ref, payload_jsonb, relevance_score, created_at)
- `documents` (id, org_id, source_id, external_id, title, doc_type, permission_ref, ingested_at)
- `document_chunks` (id, document_id, chunk_index, content, metadata_jsonb, token_count)
- `citations` (id, org_id, response_id, source_type, source_ref, span_start, span_end, confidence)
- `agent_runs` (id, org_id, agent_type, trigger_type, status, started_at, ended_at)
- `agent_actions` (id, agent_run_id, action_type, target_system, payload_jsonb, outcome, idempotency_key)
- `audit_logs` (id, org_id, actor_type, actor_id, event_type, object_ref, payload_jsonb, created_at)

Indexes:
- B-tree on all foreign keys and high-selectivity status/time columns.
- GIN on JSONB metadata columns used in filters.

Tenant safety:
- include `org_id` in all tenant data tables
- apply row-level security policies by `org_id`

## 2.2 pgvector (Semantic Retrieval)

Add to `document_chunks`:
- `embedding vector(1536)` (or chosen model dimension)

Indexes:
- HNSW or IVFFlat index on `embedding`
- compound filtering strategy: `org_id + metadata` prefilter before vector ranking

Retrieval strategy:
1. metadata/ACL prefilter
2. vector similarity shortlist
3. lexical rerank
4. graph-aware rerank

## 2.3 Neo4j (Knowledge Graph)

Node labels:
- `Person`, `Team`, `Vendor`, `Customer`, `Contract`, `Invoice`, `Workflow`, `WorkflowStep`, `Decision`, `Incident`, `Policy`, `KPI`

Relationship types:
- `OWNS`, `PART_OF`, `APPROVES`, `BLOCKED_BY`, `CAUSED_BY`, `IMPACTS`, `REFERENCES`, `VIOLATES`, `RELATED_TO`, `PRECEDES`

Graph query use cases:
- find root-cause chains for close delays
- find recurring AP exception patterns by vendor/team
- find decisions that changed cash outcomes

---

## 3) API Contracts (v1)

Base path: `/api/v1`

### Auth and Context
- `GET /me` -> current user, roles, org context
- `GET /permissions/evaluate` -> policy decision for object/action

### Sources and Ingestion
- `POST /sources` -> create source connection
- `GET /sources` -> list source health/sync status
- `POST /sources/{sourceId}/sync` -> trigger incremental sync
- `GET /ingestion-runs` -> run history with failures

### Knowledge and Retrieval
- `POST /query/context` -> hybrid retrieval for finance question
- `POST /query/explain` -> answer + citations + confidence + graph trace
- `GET /documents/{id}/citations` -> traceable source references

### Workflows and Tasks
- `GET /workflows` -> filtered workflow states (AP/AR/Close/Cash/etc.)
- `POST /workflows/{id}/actions` -> execute approved action
- `GET /workflows/{id}/timeline` -> state and decision history

### Decisions and Memory
- `POST /decisions` -> record decision with rationale and linked evidence
- `GET /decisions` -> list/search decisions by workflow/entity
- `GET /memory` -> scoped memory retrieval by subject/type
- `POST /memory` -> write curated memory record

### Agent Runtime
- `POST /agents/run` -> trigger agent run
- `GET /agents/runs/{runId}` -> run state and outputs
- `POST /agents/runs/{runId}/approve` -> human approval gate

### Audit
- `GET /audit/logs` -> immutable action trail with filters

Response contract requirements:
- include `request_id`
- include `citations[]` where AI-generated text exists
- include `confidence` and `verification_status`

---

## 4) Queue and Event Design

Transport choice for MVP:
- Redis + BullMQ

Queue groups:
- `ingestion.sync`
- `ingestion.retry`
- `processing.chunk`
- `processing.embed`
- `processing.extract`
- `graph.upsert`
- `memory.write`
- `retrieval.precompute`
- `agent.run`
- `agent.action`
- `notifications.dispatch`
- `audit.persist`

Dead-letter queues:
- one DLQ per critical queue (`*.dlq`)

Event envelope (standard):
- `event_id`
- `event_type`
- `org_id`
- `source`
- `occurred_at`
- `trace_id`
- `payload`
- `schema_version`

Key event types:
- `source.sync.started`
- `source.sync.completed`
- `source.sync.failed`
- `document.ingested`
- `chunk.embedded`
- `entity.resolved`
- `workflow.blocker.detected`
- `decision.recorded`
- `agent.run.started`
- `agent.run.completed`
- `agent.action.requested`
- `agent.action.approved`
- `agent.action.executed`
- `policy.violation.detected`

Delivery guarantees:
- at-least-once delivery
- idempotent consumers with idempotency keys
- exponential backoff retries

---

## 5) Sprint-wise Engineering Tasks (12 Sprints)

Assumption: 2-week sprints, small cross-functional team.

### Sprint 1
- repo scaffolding, environments, CI/CD
- auth integration and tenant model
- base schema migrations

### Sprint 2
- source connector framework
- ERP + document source connector v1
- ingestion run tracking + retries

### Sprint 3
- bank feed connector
- identity resolution v1
- canonical finance entities ingestion

### Sprint 4
- chunking + embeddings pipeline
- metadata extraction pipeline v1
- vector index setup and benchmark

### Sprint 5
- graph schema and upsert jobs
- relationship extraction rules
- graph query API v1

### Sprint 6
- hybrid retrieval API
- citation generation
- confidence and verification status computation

### Sprint 7
- memory service v1 (short-term + decision memory)
- memory write policies and retrieval hooks
- memory quality evaluation scripts

### Sprint 8
- AP exception agent
- human approval gate
- action logging and idempotent execution

### Sprint 9
- close orchestration agent
- workflow timeline UI endpoints
- blocker detection rules

### Sprint 10
- cash risk and collections alert agent
- notification dispatch service
- role-specific dashboards API

### Sprint 11
- RBAC/ABAC hardening and source ACL enforcement
- audit log completeness checks
- penetration/security testing fixes

### Sprint 12
- pilot rollout with 1-2 design partners
- reliability/performance tuning
- KPI instrumentation and feedback loop

---

## 6) Definition of Done for MVP

MVP is complete when:
- top 3 workflows (close, AP exceptions, cash risk alerts) run in production for pilot users
- every AI response includes source citations and confidence
- permission leakage tests pass across roles
- end-to-end audit trail exists for all agent actions
- finance team reports measurable time saved in weekly operations

---

## 7) Finance Model Training and Accuracy Framework

Goal: maximize finance accuracy with a safe continuous-learning system that improves from real usage without unsafe autonomous drift.

## 7.1 Training Philosophy

Use a layered approach:
- layer 1: base frontier model (general reasoning)
- layer 2: retrieval from trusted finance knowledge sources
- layer 3: policy and verification guardrails
- layer 4: feedback-driven adaptation
- layer 5: selective fine-tuning for stable tasks

Guiding rule:
- prefer retrieval updates for changing finance knowledge
- use model fine-tuning only for stable patterns (classification, formatting, routing)

---

## 7.2 Knowledge Sources for Finance Skills

### Internal (high-priority)
- SOPs, policy manuals, close playbooks
- AP/AR exception logs and resolutions
- audit findings and remediation notes
- decision records with rationale
- anonymized historical tickets and outcomes

### External trusted (licensed/permitted use only)
- accounting standards guidance
- regulator/tax authority publications
- legal-compliance advisories
- high-quality domain references for interpretation

Source governance requirements:
- maintain source registry with owner, license, version, effective dates
- assign trust score per source
- deprecate stale sources with expiry workflows

---

## 7.3 Dataset Schema (Training + Evaluation)

Create datasets with explicit schema and versioning.

### A. `qa_gold_examples`
- `id`
- `org_scope` (global, industry, tenant)
- `question`
- `expected_answer`
- `expected_citations[]`
- `difficulty` (easy/medium/hard)
- `topic` (AP, AR, close, tax, treasury, etc.)
- `policy_risk_level` (low/medium/high)
- `created_by`
- `reviewed_by`
- `approved_at`
- `dataset_version`

### B. `task_classification_examples`
- `id`
- `input_text`
- `label` (exception_type, workflow_state, urgency, owner_team)
- `label_confidence`
- `review_status`
- `dataset_version`

### C. `action_outcome_examples`
- `id`
- `context_snapshot_ref`
- `recommended_action`
- `human_decision` (accepted/rejected/modified)
- `final_outcome`
- `outcome_score` (business impact proxy)
- `review_notes`

### D. `retrieval_judgments`
- `id`
- `query`
- `retrieved_context_ids[]`
- `relevant_context_ids[]`
- `precision_at_k`
- `reviewer`

### E. `safety_events`
- `id`
- `event_type` (hallucination, permission leak attempt, policy breach, unsafe action)
- `severity`
- `detected_by`
- `resolution_status`

---

## 7.4 Evaluation Metrics (Release Gate)

Every model/prompt/retrieval update must pass these thresholds.

### Answer Quality
- factual_accuracy
- citation_precision
- citation_recall
- groundedness_score (answer supported by provided evidence)
- unsupported_claim_rate

### Retrieval Quality
- recall_at_k
- precision_at_k
- MRR/NDCG
- ACL_filter_correctness

### Workflow/Agent Quality
- task_success_rate
- approval_reversal_rate
- manual_override_rate
- time_to_resolution

### Safety and Trust
- hallucination_rate
- policy_violation_rate
- permission_violation_rate
- high-risk_action_block_rate

### Business Impact
- close_cycle_time_reduction
- AP_exception_backlog_reduction
- collection_effectiveness_improvement
- finance_user_trust_score

Suggested initial release gates:
- citation_precision >= 0.95
- groundedness_score >= 0.90
- permission_violation_rate = 0 for critical paths
- hallucination_rate <= 0.03 on gold set

---

## 7.5 Feedback Loop Design (Human-in-the-Loop)

Capture structured feedback from each interaction:
- user rating (helpful/not helpful)
- correction text
- citation correctness flag
- action acceptance/rejection
- escalation reason

Processing loop:
1. ingest feedback events
2. auto-triage into retrieval issue, reasoning issue, policy issue, or data quality issue
3. create labeled training/eval candidates
4. expert review queue (finance SMEs)
5. approved examples go to next dataset version
6. run offline eval
7. promote update only if release gates pass

---

## 7.6 "Auto-Train Itself" Design (Safe Continuous Learning)

The system should not self-modify model behavior directly in production without controls.

Use controlled continuous learning:
- online learning target: retrieval ranking, memory freshness, and source trust weighting
- offline learning target: prompt changes and fine-tuning candidates
- promotion requires human review + automated eval pass

### Continuous Learning Pipeline
1. collect production telemetry and feedback
2. generate candidate improvements (new examples, prompt variants, ranker weights)
3. run shadow evaluation against gold and recent hard cases
4. run safety regression tests
5. require approval from model governance role
6. roll out with canary release
7. monitor rollback triggers

### Hard Safety Constraints
- no autonomous fine-tune deployment without human approval
- no bypass of permission and policy filters
- no learning from unresolved or low-confidence responses
- no training on raw sensitive data without anonymization policy

---

## 7.7 Step-by-Step Implementation Checklist

### Phase A: Foundations
- [ ] establish dataset registry and versioning (`v1`, `v2`, ...)
- [ ] define gold set (minimum 500 high-value finance questions)
- [ ] implement citation and confidence in all AI responses
- [ ] instrument full tracing (`request_id`, retrieval set, model output, final action)

### Phase B: Evaluation System
- [ ] build offline eval runner (daily scheduled)
- [ ] build metric dashboards and release gates
- [ ] create hard-case suite from production errors
- [ ] implement safety regression suite

### Phase C: Feedback and Learning
- [ ] add in-product feedback controls for finance users
- [ ] auto-create labeling tasks from negative feedback
- [ ] build reviewer queue for finance SMEs
- [ ] publish approved examples into next dataset version

### Phase D: Controlled Adaptation
- [ ] deploy retrieval re-ranker updates via canary
- [ ] deploy prompt updates via A/B tests
- [ ] test selective fine-tuning for classification subtasks
- [ ] enforce governance approval workflow before promotion

### Phase E: Operations
- [ ] weekly model review with finance + engineering + compliance
- [ ] monthly policy and source trust review
- [ ] quarterly architecture and risk posture review

---

## 8) UI Plan - Two Dashboards

Need two separate dashboard experiences:
- Platform Admin Dashboard (for you/your team)
- Company Workspace Dashboard (for each customer company)

## 8.1 Platform Admin Dashboard (Control Plane)

Primary users:
- founder/admin
- platform operations
- ML/retrieval governance owners

Core modules:

### A. Tenant and Onboarding Management
- create/manage tenant accounts
- connector setup progress
- environment health and readiness

### B. Source and Sync Operations
- source status by tenant
- sync success/failure trends
- backlog and retry queues
- DLQ inspection and replay

### C. Model and Retrieval Governance
- model/prompt versions by tenant
- evaluation scorecards and release gate status
- canary rollout controls and rollback actions

### D. Safety and Compliance Center
- policy violations
- permission leakage alerts
- audit trail explorer
- incident response workflows

### E. Billing and Usage
- token usage, compute, storage
- per-tenant cost and margin visibility
- plan limits and overage controls

### F. Support and Debug Console
- tenant-level request tracing
- agent run replay
- citation and retrieval diagnostics

Admin KPIs:
- tenant activation rate
- sync reliability
- hallucination and policy incident trends
- unit economics per tenant

---

## 8.2 Company Workspace Dashboard (Tenant Plane)

Primary users:
- CFO, controller, finance manager
- AP/AR specialists
- finance operations analysts

Core modules:

### A. Finance Operations Command Center
- open blockers by workflow
- daily priorities and SLA breaches
- cash and collections risk indicators

### B. Workflow Boards
- AP exceptions board
- close management board
- AR collections board
- compliance and filing board

### C. Decision Timeline
- what was decided
- by whom
- why (with citations)
- downstream impact

### D. AI Copilot and Action Center
- role-aware assistant panel
- suggested actions with confidence and evidence
- approval queue for high-risk actions

### E. Source Explorer
- data freshness and source lineage
- permissions-aware source drill-down
- reference documents and transaction links

### F. Performance and Outcome Analytics
- close duration trend
- AP cycle time
- DSO trend and collections performance
- workflow bottleneck heatmap

Tenant KPIs:
- time saved per workflow
- exception resolution speed
- forecast accuracy uplift
- user trust and adoption score

---

## 8.3 Role-Based UX Matrix

### Platform Admin Roles
- `platform_owner`: full control across tenants
- `ops_admin`: ingestion and operational controls
- `governance_admin`: model release and policy controls
- `support_admin`: read-heavy debug with controlled write actions

### Tenant Roles
- `tenant_admin`: tenant config and access
- `cfo`: strategic analytics + approvals
- `controller`: close and controls focus
- `ap_manager` / `ar_manager`: function-specific operations
- `finance_analyst`: analysis and reporting

---

## 8.4 UI Delivery Roadmap

### UI Sprint 1-2
- auth, tenant switcher, base navigation shell
- platform admin source health screen
- tenant command center skeleton

### UI Sprint 3-4
- AP exceptions board
- close board
- action approvals UI

### UI Sprint 5-6
- decision timeline
- source explorer with citations
- retrieval trace panel (admin)

### UI Sprint 7-8
- governance scorecards
- model release controls
- billing/usage dashboards

### UI Sprint 9-10
- advanced analytics and KPI trend pages
- role-specific layout refinements
- accessibility and performance hardening

---

## 8.5 UI Technical Notes

- frontend: Next.js with route groups for `admin` and `workspace`
- design system: shared component library with strict role-aware guards
- API access: BFF layer enforces tenant + role claims
- realtime: WebSocket/SSE for queue status and workflow updates
- auditing: critical UI actions produce signed audit events


