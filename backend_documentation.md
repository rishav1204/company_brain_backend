# Backend Integration Documentation (Frontend / UI Team)

This document is the integration guide for teams building the **frontend separately** from this repository.

## Frontend vs Backend — How We Build

| Layer | Location | Status |
|-------|----------|--------|
| **Backend API** | `backend/apps/api` (this repo) | Implemented — FastAPI, Postgres, Redis, Neo4j |
| **Frontend (Admin + Workspace)** | **Separate app/repo** (planned: `apps/web` per root README) | **Not in this repo yet** |

The backend is an **API-first BFF**. The UI team should:

- Call REST endpoints under `/api/v1`
- Use **Bearer JWT** (OIDC in production, dev login locally)
- Treat `org_id` as the tenant key (same as `company_id` in architecture docs)
- Render `confidence`, `verification_status`, and `citations[]` on all AI surfaces
- Implement human-in-the-loop approval UI for agent runs in `pending_human_approval` state

There is **no Next.js app in this monorepo today**. Build the UI in your own project and point it at the API base URL (e.g. `http://localhost:8000` locally, or your deployed gateway URL).

**Browser CORS:** The API does not currently configure CORS middleware. For local UI development, either:

- Proxy `/api/v1` through your frontend dev server (recommended), or
- Add CORS at the API gateway / ingress layer in deployment

---

## 1) Backend Overview

### Runtime stack

- **API:** FastAPI (`backend/apps/api`)
- **Database:** PostgreSQL + pgvector (required for production paths)
- **Queue / events:** Redis (main queue + event topology + DLQ)
- **Graph:** Neo4j (relationship intelligence)
- **Workers:** `backend/cmd/worker.py`, `backend/cmd/scheduler.py`
- **Deploy:** Docker + Helm (`backend/charts/`), GitHub Actions CI/deploy

### Logical modules (implementation lives in `apps/api/app/services/`)

| Concern | Service areas |
|---------|----------------|
| Auth / OIDC | `jwt_auth.py`, `oidc_service.py`, `auth.py` routes |
| Policy / RBAC / ABAC | `policy_service.py`, `object_context.py` |
| Sources / ingestion | `repositories.py`, `ingestion_service.py`, `connectors.py` |
| Retrieval | `retrieval_pipeline.py`, `retrieval_service.py`, pgvector |
| Agents | `langgraph_runner.py`, `action_service.py`, `agents.py` routes |
| Events | `event_bus.py`, `event_queue.py`, `event_consumers.py` |
| Graph | `neo4j_service.py`, `graph_extraction_service.py` |
| Training / governance | `training_eval_service.py`, `learning_governance_service.py` |
| Observability | `metrics.py`, `otel.py`, `observability_service.py` |

`backend/internal/*` folders are **architecture boundaries (documentation only)** — all runnable code is in `apps/api`.

### Health endpoints (no auth)

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness — `{ "status": "ok" }` |
| `GET /ready` | Readiness — Postgres, Redis, observability checks |

---

## 2) Authentication & Session

### Production path (recommended for UI)

1. `GET /api/v1/auth/oidc/start?redirect_uri=...` → receive `authorize_url`, `state`
2. Redirect user to IdP
3. IdP callback → `POST /api/v1/auth/oidc/callback` with `{ "code", "state" }`
4. Store `access_token` from response
5. All API calls: `Authorization: Bearer <access_token>`
6. Session refresh: `POST /api/v1/auth/oidc/refresh` with `refresh_token`
7. Logout: `POST /api/v1/auth/oidc/logout`
8. Revoke: `POST /api/v1/auth/oidc/revoke`

JWT claims (configurable via env):

- Tenant: `org_id` (`JWT_TENANT_CLAIM`)
- User: `sub` (`JWT_USER_CLAIM`)
- Roles: `roles` (`JWT_ROLES_CLAIM`)

Production requirements:

- `JWT_REQUIRE_JWKS_IN_PROD=true` — tokens verified via JWKS
- OIDC-issued session tokens align with API JWT verification path
- Revoked tokens (`jti` in Redis) are rejected on bearer validation

### Local development path

Dev routes are gated by `ENABLE_DEV_AUTH_ROUTES` and disabled in prod when `DISABLE_DEV_AUTH_ROUTES_IN_PROD=true`.

1. `POST /api/v1/auth/dev/create-user` — seed a dev user
2. `POST /api/v1/auth/password/login` — get JWT (`password: dev-password` if user not in store)
3. `GET /api/v1/me` — hydrate session

### Auth modes

| Mode | Behavior |
|------|----------|
| `AUTH_MODE=bearer_only` (default) | Bearer token required on all `/api/v1/*` routes |
| Header fallback (non-bearer_only) | `X-Org-Id`, `X-User-Id`, `X-Roles` for local testing only |

Missing/invalid auth → `401`. Missing roles → `403`.

### Session context endpoint

`GET /api/v1/me`

Response includes: `user_id`, `org_id`, `roles`, `request_id`, `confidence`, `verification_status`.

### Permission evaluation (object-context aware)

`GET /api/v1/permissions/evaluate?object_type=invoice&object_id=<uuid>&action=approve_payment`

Response:

```json
{
  "request_id": "...",
  "allowed": false,
  "reason": "human_approval_required",
  "checks": ["object_context_resolved", "rbac_checked", "approval_required"],
  "object_context": {
    "object_type": "invoice",
    "object_id": "...",
    "amount": 75000.0,
    "vendor_risk": "high",
    "status": "Pending"
  },
  "confidence": 0.99,
  "verification_status": "object_context_policy_checked"
}
```

**UI guidance:** Call this before enabling destructive/high-risk action buttons. Gate CTAs on `allowed === true`.

Supported object types for context resolution: `invoice`, `workflow` (loaded from Postgres). Other types use generic policy rules.

---

## 3) Standard Response Contract

All product endpoints should return:

| Field | UI usage |
|-------|----------|
| `request_id` | Support/debug correlation; show in error toasts |
| `confidence` | Display near AI recommendations (0–1) |
| `verification_status` | Machine-readable state for badges/chips |
| `citations[]` | Source trace panel (retrieval/explain flows) |

Common `verification_status` values:

- `verified`, `policy_checked`, `human_approved`, `idempotent_replay`
- `abac_denied`, `policy_blocked_pending_approval`
- `pending_human_approval` (agent runs)
- `observability_stack_status`, `feedback_recorded_and_triaged`, etc.

Rate limiting: HTTP `429` with `Retry-After` header (org-level budget).

---

## 4) API Reference by UI Surface

Base path: **`/api/v1`**

All endpoints below require authentication unless noted.

### 4.1 Workspace — Workflows & Action Center

| Method | Path | UI surface |
|--------|------|------------|
| GET | `/workflows` | AP / close / AR / cash boards |
| POST | `/workflows/{workflow_id}/actions` | Action center (approve, escalate, reassign) |
| GET | `/workflows/{workflow_id}/timeline` | Decision / activity timeline |

**Workflow action request** — include in `parameters`:

- `idempotency_key` — safe retries; replay returns `idempotent_replay: true`
- Sensitive fields (`bank_account_number`, `tax_id`, `ssn`, `salary`) — blocked unless role allows

**Policy-blocked response** (no error throw):

```json
{
  "accepted": false,
  "requires_human_approval": true,
  "verification_status": "policy_blocked_pending_approval"
}
```

### 4.2 Workspace — Copilot & Retrieval

| Method | Path | UI surface |
|--------|------|------------|
| POST | `/query/context` | Copilot context panel |
| POST | `/query/explain` | Explainability drawer |
| GET | `/documents/{document_id}/citations` | Citation drill-down |
| POST | `/retrieval/eval` | Admin/eval tooling |

**`POST /query/context` body:**

```json
{
  "query": "Why is invoice INV-123 blocked?",
  "subject_ref": "optional-workflow-or-invoice-id",
  "top_k": 5,
  "metadata_filter": {}
}
```

Response includes `context[]`, `citations[]`, `confidence`, `verification_status`.

Retrieval is **permission-aware**: user's `source_acl` and ABAC attrs filter results before LLM context is built.

**Note:** `GET /documents/{id}/citations` currently returns a **stub** citation payload. Prefer citations from `/query/context` and `/query/explain` until DB-backed citations land.

### 4.3 Workspace — Agents & Approval Queue

| Method | Path | UI surface |
|--------|------|------------|
| POST | `/agents/run` | Trigger agent from workflow/exception |
| GET | `/agents/runs/{run_id}` | Run detail / progress |
| POST | `/agents/runs/{run_id}/approve` | Human approval queue |

**Supported `agent_type` values:**

| Value | Domain |
|-------|--------|
| `ap_exception_agent` | AP exception triage |
| `close_orchestration_agent` | Month-end close orchestration |
| `cashflow_risk_agent` | Cash / collections risk alerts |

**Run request example:**

```json
{
  "agent_type": "ap_exception_agent",
  "trigger_type": "manual",
  "payload": {
    "workflow_id": "<uuid>",
    "object_type": "workflow",
    "object_id": "<uuid>",
    "action": "approve_payment",
    "amount": 12000,
    "vendor_risk": "medium"
  }
}
```

**Run statuses UI must handle:**

| Status | UI behavior |
|--------|-------------|
| `completed` | Show success + tool results |
| `pending_human_approval` | Show approval queue item — **do not assume actions ran** |
| `failed` | Show `failure_contract` from `outputs.flow_result` if present |

**Approval request:**

```json
{
  "approved_by": "<user_id>",
  "comment": "Reviewed vendor contract"
}
```

Response includes `executed_actions[]` with per-action results. Approver must have `tenant_admin`, `controller`, or `cfo` role (SoD rules apply).

### 4.4 Workspace — Decisions & Memory

| Method | Path | UI surface |
|--------|------|------------|
| POST | `/decisions` | Record decision rationale |
| GET | `/decisions` | Decision timeline |
| GET | `/memory?subject_ref=&memory_type=` | Memory context cards |
| POST | `/memory` | Persist operational memory |

### 4.5 Workspace — Company / Tenant Reports

| Method | Path | UI surface |
|--------|------|------------|
| GET | `/companies/{company_id}/invoices/{invoice_id}` | Invoice detail |
| POST | `/companies/{company_id}/invoices` | Create invoice |
| POST | `/companies/{company_id}/workflows/{workflow_id}/actions` | Company-scoped actions (policy check only — prefer `/workflows/{id}/actions` for execution) |
| GET | `/companies/{company_id}/reports/close-status` | CFO close dashboard |

`company_id` = tenant `org_id` (UUID).

### 4.6 Workspace — Graph Intelligence

| Method | Path | UI surface |
|--------|------|------------|
| GET | `/graph/queries/invoice-exceptions?subject_ref=` | Invoice exception graph |
| GET | `/graph/queries/close-root-cause?limit=` | Close blocker root cause |
| GET | `/graph/queries/ap-patterns?limit=` | AP exception patterns |
| GET | `/graph/queries/decision-impact?limit=` | Decision → KPI impact |

Admin/ops:

| POST | `/graph/bootstrap` | Neo4j schema constraints |
| POST | `/graph/extract` | Postgres → Neo4j relationship sync |

### 4.7 Admin — Sources & Ingestion

| Method | Path | UI surface |
|--------|------|------------|
| POST | `/sources` | Connector setup |
| GET | `/sources` | Source list |
| POST | `/sources/{source_id}/sync` | Manual sync trigger |
| GET | `/ingestion-runs` | Sync history |
| POST | `/ingestion/runs/start` | Programmatic run start |
| POST | `/ingestion/runs/complete` | Run completion |
| POST | `/identity/resolve` | Entity dedupe / canonical identity |
| POST | `/connectors/run` | Run connector pipeline |
| POST | `/ingestion/workers/embeddings/ingest` | Document embedding ingest |

Connector types: `erp`, `bank`, `crm`, `docs`, `ticketing`, `slack`, `email`, `jira`, `linear`.

### 4.8 Admin — Audit & Compliance

| Method | Path | UI surface |
|--------|------|------------|
| GET | `/audit/logs` | Immutable audit explorer |

Every agent action, approval, governance step, and source change writes audit records.

### 4.9 Admin — Observability

| Method | Path | UI surface |
|--------|------|------------|
| GET | `/observability/status` | Stack health dashboard |
| GET | `/metrics` | JSON runtime counters + queue lag |
| GET | `/metrics/prometheus` | Prometheus scrape format |
| POST | `/observability/probe` | Log-sink connectivity test |
| GET | `/events/recent?limit=20` | Recent event stream (process-local snapshot) |
| GET | `/queue/topology` | Queue/topic map |

Key metrics for admin dashboards:

- `request_count`, `request_error_count`
- `agent_runs`, `retrieval_queries`, `llm_failures`
- `queue_retries`, `queue_dlq_count`, `queue_lag_by_queue`
- `log_sink_success_count`, `trace_span_count`
- `otel_enabled`, `prod_requirements_met`

### 4.10 Admin — Training, Eval & Model Governance

| Method | Path | UI surface |
|--------|------|------------|
| POST | `/training/feedback` | In-product feedback capture |
| POST | `/training/feedback/triage` | Batch triage feedback → labeling tasks |
| GET | `/training/labeling-tasks?status=pending_review` | SME review queue |
| POST | `/training/labeling-tasks/{task_id}/approve` | Approve labeled example |
| POST | `/training/qa-gold` | Add gold Q&A example |
| GET | `/training/qa-gold` | List gold examples |
| POST | `/training/retrieval-judgments` | Add retrieval judgment |
| GET | `/training/retrieval-judgments` | List judgments |
| POST | `/training/safety-events` | Record safety incident |
| POST | `/training/eval-runs/start` | Start eval run |
| POST | `/training/eval-runs/{run_id}/complete` | Complete eval + metrics |
| POST | `/training/governance/cycles/start` | Start promotion cycle |
| GET | `/training/governance/cycles` | List governance cycles |
| POST | `/training/governance/cycles/{id}/shadow-eval` | Run shadow evaluation |
| POST | `/training/governance/cycles/{id}/approve-promotion` | Governance approval (`governance_admin` role) |
| POST | `/training/governance/cycles/{id}/canary` | Advance canary % |
| POST | `/training/governance/cycles/{id}/rollback` | Rollback promotion |

**Feedback payload example** (for thumbs-down / correction UI):

```json
{
  "event_type": "not_helpful",
  "created_by": "user-123",
  "payload_jsonb": {
    "query": "AP approval threshold",
    "candidate_ref": "doc:policy-ap",
    "correction": "Threshold is $50k not $25k",
    "citation_correct": false,
    "rating": 1
  }
}
```

Feedback auto-triggers triage into labeling tasks on create.

**Governance cycle states:** `labeling_review` → `promotion_review` → `canary_rollout` → `promoted` (or `rejected` / `rolled_back`).

### 4.11 Admin — Queue & Ops (internal tooling)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/queue/enqueue` | Test enqueue |
| POST | `/queue/process-next` | Drain main queue |
| POST | `/ops/worker/run-once` | Single worker tick |
| POST | `/ops/worker/run-batch` | Batch worker drain |
| POST | `/ops/scheduler/run-once` | Memory decay job |
| POST | `/memory/decay/run` | Manual memory lifecycle |

Ops routes may be disabled in production via `ENABLE_WORKER_ROUTES=false`.

---

## 5) Database & Migrations

Apply before running API against real data:

```bash
python backend/scripts/run_migrations.py \
  --dsn "postgresql://postgres:postgres@localhost:5432/company_brain" \
  --migrations-dir "backend/migrations"
```

| Migration | Adds |
|-----------|------|
| `001_init.sql` | Core schema, pgvector, RLS, finance entities, agents, audit |
| `002_training_eval.sql` | QA gold, retrieval judgments, safety events, eval runs |
| `003_connector_sync.sql` | Connector CDC sync state + dedupe ledger |
| `004_benchmark_org_seed.sql` | Benchmark org seed |
| `005_tenant_b_seed.sql` | Second tenant for isolation testing |
| `006_rls_hardening.sql` | FORCE RLS, `app_current_org_id()`, WITH CHECK policies |
| `007_canonical_finance_model.sql` | Contracts, purchase orders, payments |
| `008_learning_governance.sql` | Labeling tasks, governance cycles |

All tenant tables enforce org isolation via Postgres RLS.

---

## 6) Event Envelope (for trace correlation)

Published events use:

```json
{
  "event_id": "uuid",
  "event_type": "agent.run.started",
  "topic": "finance.agent",
  "org_id": "tenant-uuid",
  "source": "api.agents",
  "occurred_at": "ISO-8601",
  "trace_id": "request-uuid",
  "principal": { "user_id": "...", "roles": ["..."], "attrs": {} },
  "payload": {},
  "schema_version": "v1"
}
```

UI can correlate user actions via shared `request_id` / `trace_id` in support tooling. Admin `/events/recent` shows a process-local snapshot (not durable cross-replica).

---

## 7) Suggested UI Integration Order

1. **Auth shell** — OIDC or dev login → `GET /me` → store token
2. **Permission gates** — `GET /permissions/evaluate` on action buttons
3. **Workflow board** — `GET /workflows`, timeline, actions
4. **Copilot panel** — `POST /query/context`, `/query/explain` + citations UI
5. **Agent approval queue** — run status polling + `POST .../approve`
6. **Decisions & memory** — timeline and context cards
7. **Audit explorer** — `GET /audit/logs`
8. **Admin: sources** — connector setup and ingestion status
9. **Admin: governance** — feedback, labeling queue, promotion cycles
10. **Admin: observability** — metrics and status dashboards

---

## 8) Role Matrix (for UI routing)

Common tenant roles referenced by policy:

| Role | Typical UI access |
|------|-------------------|
| `tenant_admin` | Full tenant admin |
| `cfo`, `controller` | Approvals, high-risk actions |
| `ap_preparer` | Prepare — **cannot** approve payments (SoD) |
| `governance_admin` | Model promotion approval |
| `analyst` | Read-heavy, limited actions |

Platform admin UI (multi-tenant ops) is a separate surface — use observability, queue, governance, and audit APIs.

---

## 9) Local Development Setup (Frontend Team)

### Database — Cloud Postgres (recommended, no Docker)

Use a managed Postgres with **pgvector** enabled. Good options:

| Provider | pgvector | Free tier |
|----------|----------|-----------|
| [Neon](https://neon.tech) | Yes (enable in dashboard) | Yes |
| [Supabase](https://supabase.com) | Yes | Yes |

**Neon setup (5 minutes):**

1. Create a project at [neon.tech](https://neon.tech)
2. In the Neon dashboard: **Extensions → enable `vector`**
3. Copy the connection string (use the **pooled** or **direct** URL — both work for dev)
4. Paste into `backend/apps/api/.env`:

```env
POSTGRES_DSN=postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
POSTGRES_REQUIRE_TLS=true
DEV_USE_POSTGRES=true
```

5. Run migrations from the repo root:

```powershell
cd d:\new_project\backend
python scripts/run_migrations.py --dsn "YOUR_POSTGRES_DSN_HERE" --migrations-dir migrations
```

6. Restart the API and verify:

```powershell
curl http://127.0.0.1:8000/ready
```

Expect `"postgres": "ok"` in the response.

**Dev login org:** JWTs use tenant UUID `11111111-1111-4111-8111-111111111111` (seeded by migration `004_benchmark_org_seed.sql`).

**Without Postgres:** If `DEV_USE_POSTGRES=false` or DSN is missing, workflow APIs return sample dev data instead of real DB rows.

### Infrastructure (optional — Docker)

```bash
docker compose -f backend/infra/docker-compose.yml up -d
```

Starts Postgres (pgvector), Redis, Neo4j locally. **Not required** if you use cloud Postgres.

### API

```bash
cd backend/apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Set POSTGRES_DSN, REDIS_URL, OPENAI_API_KEY (optional for LLM features)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run migrations (see section 5).

### Verify

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/ready`
- OpenAPI: `http://localhost:8000/docs` (Swagger UI)

### Frontend proxy (Express on port 3003)

The UI dev server proxies `/api/v1` → `http://localhost:8000`. **Restart the frontend dev server** after proxy config changes.

**Dev login payload** (minimal — `org_id` and `roles` are optional server defaults):

```json
{
  "email": "dev@example.com",
  "password": "dev-password"
}
```

Optional fields: `org_id` (default benchmark UUID), `roles` (default `["tenant_admin"]`).

**Common login 401 cause:** Express `http-proxy-middleware` strips the `/api/v1` mount prefix when forwarding. Backend expects full paths like `/api/v1/auth/password/login`. Both backend middleware and frontend proxy (`new_project_frontend/server/_core/apiProxy.ts`) handle this — ensure both repos are up to date and restart the frontend after pulling proxy fixes.

```js
// vite.config.js
server: {
  proxy: {
    '/api/v1': 'http://localhost:8000'
  }
}
```

---

## 10) Known Limitations (UI Team Should Know)

| Item | Impact on UI |
|------|----------------|
| No frontend in this repo | Build UI separately; this doc is the contract |
| No CORS on API | Use dev proxy or gateway CORS |
| `/documents/{id}/citations` stub | Use citations from query endpoints |
| LLM features need `OPENAI_API_KEY` | Explain/agent planning fall back to rulebooks |
| Connector data is synthetic in dev | Source sync screens show pipeline status, not live ERP unless webhooks configured |
| `/events/recent` not durable | Do not build cross-session event history from this alone |
| Company workflow actions | Policy-only; use `/workflows/{id}/actions` for execution |

---

## 11) OpenAPI & Contracts

- Interactive docs: `/docs` when API is running
- Static spec: `backend/api/openapi.yaml`
- Event envelope: `backend/pkg/contracts/event_envelope.json`
- API contracts notes: `backend/pkg/contracts/api_contracts.md`

---

## 12) Implementation Status Summary

**Implemented and ready for UI integration:**

- Full REST API under `/api/v1` with JWT/OIDC auth
- Postgres-backed workflows, invoices, sources, agents, audit, memory, decisions
- Hybrid retrieval with citations and confidence
- Agent runtime with human approval gate
- Object-context permission evaluation
- Training feedback → labeling → shadow eval → governance → canary → rollback
- Observability metrics and status endpoints
- Redis event pipeline with workers
- Neo4j graph queries and extraction
- CI/deploy with migrations and smoke checks

**Built separately (not in this repo):**

- Next.js admin + workspace UI (`apps/web` per architecture roadmap)
- WebSocket/SSE live workflow updates (API is request/response today)
- Production IdP tenant configuration (backend supports Auth0-style OIDC)

This backend is **ready for frontend integration** against stable endpoint shapes and response contracts documented above.

---

## 13) Complete API Reference — Payloads & Responses

Base URL: `http://localhost:8000/api/v1` (or same-origin `/api/v1` via frontend proxy)

**Auth header (required on protected routes):** `Authorization: Bearer <access_token>`

**Standard fields on most responses:** `request_id`, `confidence`, `verification_status`

---

### Health (no auth)

#### `GET /health`

Response:

```json
{ "status": "ok", "service": "Company Brain Finance API" }
```

#### `GET /ready`

Response:

```json
{
  "status": "ready",
  "service": "Company Brain Finance API",
  "checks": { "api": "ok", "postgres": "ok", "redis": "ok", "otel_ready": "degraded", "observability": "ok" }
}
```

---

### Auth

#### `POST /auth/password/login` — **no auth required**

Request:

```json
{
  "email": "dev@example.com",
  "password": "dev-password",
  "org_id": "org-demo",
  "roles": ["tenant_admin"]
}
```

Only `email` and `password` are required. Unknown users must use password `dev-password`.

Response `200`:

```json
{
  "request_id": "login-1779526118",
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "confidence": 0.9,
  "verification_status": "dev_password_exchange"
}
```

Errors: `400` missing fields, `401` invalid credentials, `404` dev routes disabled

#### `POST /auth/dev/create-user` — **no auth required**

Request:

```json
{
  "email": "analyst@example.com",
  "password": "secret123",
  "org_id": "org-demo",
  "roles": ["analyst"],
  "display_name": "Jane Analyst"
}
```

Response `200`:

```json
{
  "request_id": "dev-create-...",
  "user_id": "uuid",
  "email": "analyst@example.com",
  "org_id": "org-demo",
  "roles": ["analyst"],
  "confidence": 0.88,
  "verification_status": "dev_user_created"
}
```

#### `GET /me` — auth required

Response:

```json
{
  "request_id": "req-...",
  "user_id": "dev@example.com",
  "org_id": "org-demo",
  "roles": ["tenant_admin"],
  "confidence": 1.0,
  "verification_status": "verified"
}
```

#### `GET /permissions/evaluate?object_type=invoice&object_id={uuid}&action=approve_payment` — auth required

Response:

```json
{
  "request_id": "req-...",
  "allowed": false,
  "reason": "human_approval_required",
  "checks": ["object_context_resolved", "rbac_checked", "approval_required"],
  "object_context": { "object_type": "invoice", "object_id": "...", "amount": 75000.0, "vendor_risk": "high", "status": "Pending" },
  "confidence": 0.99,
  "verification_status": "object_context_policy_checked"
}
```

#### `GET /auth/oidc/start?redirect_uri={url}` — **no auth required**

Response:

```json
{
  "request_id": "oidc-start-...",
  "authorize_url": "https://idp.example.com/authorize?...",
  "state": "random-state",
  "confidence": 0.98,
  "verification_status": "oidc_authorize_ready"
}
```

#### `POST /auth/oidc/callback` — **no auth required**

Request: `{ "code": "...", "state": "..." }`

Response:

```json
{
  "request_id": "oidc-callback-...",
  "access_token": "...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "auth0|123",
  "org_id": "org-uuid",
  "refresh_token": "...",
  "confidence": 0.98,
  "verification_status": "oidc_session_issued"
}
```

#### `POST /auth/oidc/refresh` — **no auth required**

Request: `{ "refresh_token": "..." }`

Response: same shape as callback (without refresh_token requirement)

#### `POST /auth/oidc/revoke` — auth required

Request: `{ "access_token": "..." }`

Response: `{ "request_id": "...", "status": "revoked", "confidence": 0.98, "verification_status": "oidc_access_token_revoked" }`

#### `POST /auth/oidc/logout` — auth required

Request: `{ "refresh_token": "...", "access_token": "..." }` (both optional)

Response: `{ "request_id": "...", "status": "logged_out", "confidence": 0.98, "verification_status": "oidc_session_terminated" }`

---

### Workflows

#### `GET /workflows` — auth required

Response:

```json
{
  "request_id": "req-...",
  "items": [
    {
      "id": "uuid",
      "workflow_type": "ap_exception",
      "state": "open",
      "owner_user_id": "user-1",
      "started_at": "2026-05-23T08:00:00Z",
      "closed_at": null
    }
  ],
  "confidence": 0.95,
  "verification_status": "verified"
}
```

#### `POST /workflows/{workflow_id}/actions` — auth required

Request:

```json
{
  "action": "approve_payment",
  "parameters": {
    "idempotency_key": "unique-key-123",
    "amount": 12000,
    "vendor_risk": "medium"
  }
}
```

Response (policy blocked):

```json
{
  "request_id": "req-...",
  "accepted": false,
  "requires_human_approval": true,
  "confidence": 0.95,
  "verification_status": "policy_blocked_pending_approval"
}
```

#### `GET /workflows/{workflow_id}/timeline` — auth required

Response:

```json
{
  "request_id": "req-...",
  "workflow_id": "uuid",
  "timeline": [
    { "event_type": "workflow.created", "occurred_at": "2026-05-23T08:00:00Z", "detail": "Workflow opened" }
  ],
  "confidence": 0.94,
  "verification_status": "verified"
}
```

---

### Agents

#### `POST /agents/run` — auth required

Request:

```json
{
  "agent_type": "ap_exception_agent",
  "trigger_type": "manual",
  "payload": {
    "workflow_id": "uuid",
    "object_type": "workflow",
    "object_id": "uuid",
    "action": "approve_payment",
    "amount": 12000,
    "vendor_risk": "medium"
  }
}
```

Agent types: `ap_exception_agent`, `close_orchestration_agent`, `cashflow_risk_agent`

Response:

```json
{
  "request_id": "req-...",
  "run_id": "uuid",
  "status": "pending_human_approval",
  "confidence": 0.95,
  "verification_status": "policy_checked"
}
```

#### `GET /agents/runs/{run_id}` — auth required

Response:

```json
{
  "request_id": "req-...",
  "run_id": "uuid",
  "agent_type": "ap_exception_agent",
  "trigger_type": "manual",
  "status": "pending_human_approval",
  "started_at": "2026-05-23T08:00:00Z",
  "ended_at": null,
  "outputs": { "flow_result": { "status": "pending_human_approval", "proposed_actions": [] } },
  "confidence": 0.94,
  "verification_status": "verified"
}
```

#### `POST /agents/runs/{run_id}/approve` — auth required

Request:

```json
{
  "approved_by": "controller@example.com",
  "comment": "Reviewed and approved"
}
```

Response:

```json
{
  "request_id": "req-...",
  "run_id": "uuid",
  "status": "approved",
  "executed_actions": [
    { "action_id": "uuid", "result": { "status": "completed", "detail": "..." } }
  ],
  "confidence": 0.97,
  "verification_status": "human_approved"
}
```

---

### Retrieval & Copilot

#### `POST /query/context` — auth required

Request:

```json
{
  "query": "Why is invoice INV-123 blocked?",
  "subject_ref": "workflow-uuid",
  "top_k": 5,
  "metadata_filter": {}
}
```

Response:

```json
{
  "request_id": "req-...",
  "context": ["chunk text 1", "chunk text 2"],
  "citations": [
    { "source_type": "document", "source_ref": "doc:policy-ap", "confidence": 0.92, "span_start": 0, "span_end": 120 }
  ],
  "confidence": 0.88,
  "verification_status": "retrieval_completed"
}
```

#### `POST /query/explain` — auth required

Request: `{ "query": "Explain close blocker", "subject_ref": "workflow-uuid" }`

Response:

```json
{
  "request_id": "req-...",
  "answer": "The close is blocked because...",
  "graph_trace": ["Invoice -> Vendor -> Exception"],
  "citations": [],
  "confidence": 0.85,
  "verification_status": "explain_completed"
}
```

#### `GET /documents/{document_id}/citations` — auth required

Response (stub):

```json
{
  "request_id": "req-...",
  "document_id": "uuid",
  "citations": [{ "source_type": "document", "source_ref": "stub", "confidence": 0.5 }],
  "confidence": 0.5,
  "verification_status": "stub_citations"
}
```

#### `POST /retrieval/eval` — auth required

Request: `{ "queries": [{ "query": "...", "relevant_refs": ["doc:1"] }] }`

Response: precision/recall/NDCG metrics + gate pass/fail

---

### Decisions & Memory

#### `POST /decisions` — auth required

Request:

```json
{
  "decision_type": "payment_approval",
  "title": "Approved vendor exception",
  "rationale": "Contract allows threshold override",
  "made_by": "cfo@example.com",
  "citations": [{ "source_type": "document", "source_ref": "doc:contract-1", "confidence": 0.95 }]
}
```

#### `GET /decisions` — auth required

Response: `{ "request_id", "items": [DecisionItem], "confidence", "verification_status" }`

#### `GET /memory?subject_ref={ref}&memory_type={type}` — auth required

#### `POST /memory` — auth required

Request:

```json
{
  "memory_type": "operational_note",
  "subject_ref": "workflow-uuid",
  "payload_jsonb": { "note": "Vendor confirmed PO match" },
  "relevance_score": 0.85
}
```

#### `POST /memory/decay/run` — auth required

Response: decay job summary

---

### Sources & Ingestion

#### `POST /sources` — auth required

Request: `{ "source_type": "erp", "config_ref": "netsuite-prod", "source_ref": "optional-external-id" }`

Response: `{ "id", "source_type", "status", "last_sync_at" }`

#### `GET /sources` — auth required

Response: `{ "request_id", "items": [SourceResponse], "confidence", "verification_status" }`

#### `POST /sources/{source_id}/sync` — auth required

Response: IngestionRunResponse

#### `GET /ingestion-runs` — auth required

#### `POST /ingestion/runs/start` — auth required

Request: `{ "source_id": "uuid", "trigger_mode": "polling" }` — modes: `webhook`, `polling`, `cdc`

#### `POST /ingestion/runs/complete` — auth required

Request: `{ "run_id": "uuid", "success": true, "error_summary": null }`

#### `POST /identity/resolve` — auth required

Request: `{ "aliases": ["ACME Corp", "Acme Corporation"], "canonical_type": "vendor", "source": "erp", "source_key": "vendor_name" }`

#### `POST /ingestion/workers/embeddings/ingest` — auth required

Request: `{ "source_id": "uuid", "title": "Policy doc", "content": "...", "doc_type": "policy", "permission_ref": null }`

#### `POST /connectors/run` — auth required

Request: `{ "connector": "erp", "mode": "polling", "source_id": "uuid" }`

Connectors: `erp`, `bank`, `crm`, `docs`, `ticketing`, `slack`, `email`, `jira`, `linear`

---

### Companies (tenant-scoped)

#### `GET /companies/{company_id}/invoices/{invoice_id}` — auth required

Response: `{ "request_id", "invoiceId", "amount", "status", "vendor", "confidence", "verification_status" }`

#### `POST /companies/{company_id}/invoices` — auth required

Request: `{ "number": "INV-001", "poId": "uuid", "vendorId": "uuid", "amount": 5000, "dueDate": "2026-06-01" }`

#### `POST /companies/{company_id}/workflows/{workflow_id}/actions` — auth required (policy check only)

Request: `{ "action": "approve_payment", "parameters": { "amount": 5000 } }`

#### `GET /companies/{company_id}/reports/close-status` — auth required

Response: close period KPI summary

---

### Graph

#### `POST /graph/bootstrap` — auth required

#### `POST /graph/extract` — auth required

#### `GET /graph/queries/invoice-exceptions?subject_ref={ref}` — auth required

#### `GET /graph/queries/close-root-cause?limit=20` — auth required

#### `GET /graph/queries/ap-patterns?limit=20` — auth required

#### `GET /graph/queries/decision-impact?limit=20` — auth required

All graph query responses: `{ "request_id", "rows"|"graph_trace", "confidence", "verification_status" }`

---

### Audit & Observability

#### `GET /audit/logs` — auth required

Response: `{ "request_id", "items": [{ "id", "actor_type", "actor_id", "event_type", "object_ref", "payload_jsonb", "created_at" }], "confidence", "verification_status" }`

#### `GET /observability/status` — auth required

#### `GET /metrics` — auth required

#### `GET /metrics/prometheus` — auth required (text/plain)

#### `POST /observability/probe` — auth required

#### `GET /events/recent?limit=20` — auth required

---

### Queue & Ops

#### `POST /queue/enqueue` — auth required

Request: `{ "idempotency_key": "key-123", "payload": { "action": "test" } }`

#### `POST /queue/process-next` — auth required

#### `GET /queue/topology` — auth required

#### `POST /ops/worker/run-once` — auth required

#### `POST /ops/worker/run-batch` — auth required

#### `POST /ops/scheduler/run-once` — auth required

---

### Training, Eval & Governance

#### `POST /training/feedback` — auth required

Request:

```json
{
  "event_type": "not_helpful",
  "created_by": "user@example.com",
  "payload_jsonb": {
    "query": "AP threshold",
    "correction": "Threshold is $50k",
    "rating": 1
  }
}
```

#### `POST /training/feedback/triage` — auth required

Request: `{ "limit": 50 }` (optional body)

#### `GET /training/labeling-tasks?status=pending_review` — auth required

#### `POST /training/labeling-tasks/{task_id}/approve` — auth required

Request: `{ "reviewer_id": "sme@example.com" }`

#### `POST /training/qa-gold` — auth required

Request: `{ "org_scope": "tenant", "question": "...", "expected_answer": "...", "expected_citations": [], "tags": ["ap"] }`

#### `GET /training/qa-gold` — auth required

#### `POST /training/retrieval-judgments` — auth required

Request: `{ "query": "...", "candidate_ref": "doc:1", "relevance_label": 3, "judged_by": "sme@example.com" }`

#### `GET /training/retrieval-judgments` — auth required

#### `POST /training/safety-events` — auth required

Request: `{ "event_type": "pii_leak", "severity": "high", "details": {} }`

#### `POST /training/eval-runs/start` — auth required

Request: `{ "run_type": "retrieval_benchmark" }`

#### `POST /training/eval-runs/{run_id}/complete` — auth required

Request: `{ "metrics_jsonb": { "precision": 0.85, "recall": 0.80 } }`

#### `POST /training/governance/cycles/start` — auth required

Request: `{ "candidate_version": "v2.1.0" }`

#### `GET /training/governance/cycles` — auth required

#### `POST /training/governance/cycles/{cycle_id}/shadow-eval` — auth required

#### `POST /training/governance/cycles/{cycle_id}/approve-promotion` — auth required (requires `governance_admin` role)

Request: `{ "approved_by": "admin@example.com", "comment": "Metrics pass gate" }`

#### `POST /training/governance/cycles/{cycle_id}/canary` — auth required

Request: `{ "canary_percent": 10 }`

#### `POST /training/governance/cycles/{cycle_id}/rollback` — auth required

Request: `{ "reason": "Regression in production metrics" }`

---

### Error responses

| Status | Shape | Meaning |
|--------|-------|---------|
| `401` | `{ "detail": "Bearer token required" }` or `{ "detail": "Missing authenticated org or bearer token" }` | Missing/invalid auth |
| `403` | `{ "detail": "..." }` | Policy/role denial |
| `404` | `{ "detail": "Not found" }` | Resource or disabled dev route |
| `422` | `{ "detail": [{ "loc", "msg", "type" }] }` | Validation error |
| `429` | `{ "detail": "Rate limit exceeded" }` + `Retry-After` header | Org rate limit |
| `503` | `{ "detail": "..." }` | Dependency unavailable |

Interactive OpenAPI with try-it-out: `http://localhost:8000/docs`

