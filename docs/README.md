# Backend Monorepo

This backend monorepo implements the finance architecture defined in `Readme_Architecture.md`.

**Complete file-by-file reference:** [`BACKEND_ARCHITECTURE.md`](BACKEND_ARCHITECTURE.md)  
**ERP master module map (planning — implement per module only):** [`ERP_MASTER_MODULE_MAP.md`](ERP_MASTER_MODULE_MAP.md)  
**Frontend architecture bible:** [`FRONTEND_ARCHITECTURE.md`](FRONTEND_ARCHITECTURE.md)  
**Frontend modules reference (APIs, screens, components):** [`FRONTEND_MODULES_REFERENCE.md`](FRONTEND_MODULES_REFERENCE.md)  
**Frontend UX documentation suite (product & UX constitution):** [`frontend-docs/README.md`](frontend-docs/README.md)

## Structure

- `apps/api` FastAPI API gateway/BFF (v1 contracts)
- `internal/db` Postgres + pgvector ownership
- `internal/graph` Neo4j graph ownership
- `internal/agent` LangGraph agent orchestration boundary
- `internal/policy` risk and permission guardrails
- `internal/events` queue/event ownership
- `pkg/contracts` event envelope and API contracts
- `api` OpenAPI specs
- `migrations` database migrations
- `infra` local infrastructure compose stack
- `config` environment-specific configs
- `charts` deployment artifacts
- `scripts` operational utilities

## Local Run

```bash
cd backend/apps/api
python -m venv .venv
source .venv/bin/activate  # on Windows use: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Set POSTGRES_DSN to your cloud Postgres URL (Neon/Supabase) and DEV_USE_POSTGRES=true
uvicorn app.main:app --reload
```

### Neon Postgres + pgvector

1. In [Neon Console](https://console.neon.tech) → your project → **Extensions** → enable **`vector`** (pgvector).
2. Copy the **pooled** connection string (`-pooler` host) into `apps/api/.env` as `POSTGRES_DSN` (must include `sslmode=require`).
3. Set `POSTGRES_REQUIRE_TLS=true` and `DEV_USE_POSTGRES=true`.
4. Run migrations from repo root:

```powershell
python backend/scripts/run_migrations.py --dsn "<paste POSTGRES_DSN from .env>" --migrations-dir backend/migrations
```

5. Start the API — `GET /ready` should report `postgres: ok`. Login: `dev@example.com` / `dev-password` (seeded in migration `009`).

If connection fails on Windows with `channel_binding=require`, remove that query param from the DSN (keep `sslmode=require`).

See `backend_documentation.md` section 9 for full steps.

## API base

- `GET /health`
- API root: `/api/v1`

## Added Coverage (Architecture Alignment)

- Company-scoped APIs:
  - `GET /api/v1/companies/{company_id}/invoices/{invoice_id}`
  - `POST /api/v1/companies/{company_id}/invoices`
  - `POST /api/v1/companies/{company_id}/workflows/{workflow_id}/actions`
  - `GET /api/v1/companies/{company_id}/reports/close-status`
- Rate limit middleware with HTTP 429 behavior
- Observability endpoints:
  - `GET /api/v1/metrics`
  - `GET /api/v1/metrics/prometheus`
  - `GET /api/v1/events/recent`
- Idempotency key support on workflow actions
- Policy-based human-approval gating
- CI workflow + pytest skeleton
- Ingestion runtime endpoints:
  - `POST /api/v1/ingestion/runs/start`
  - `POST /api/v1/ingestion/runs/complete`
  - `POST /api/v1/identity/resolve`
  - `POST /api/v1/ingestion/workers/embeddings/ingest`
- Queue reliability endpoints:
  - `POST /api/v1/queue/enqueue`
  - `POST /api/v1/queue/process-next`
- Memory lifecycle endpoint:
  - `POST /api/v1/memory/decay/run`
- Security hardening:
  - strict required auth headers (no implicit admin defaults)
  - explicit 429 response with retry hints
  - workflow idempotency tied to workflow scope
- JWT auth middleware and claim mapping:
  - `org_id` tenant claim
  - `sub` user claim
  - `roles` role claim
- OIDC authorization code flow endpoints:
  - `GET /api/v1/auth/oidc/start`
  - `POST /api/v1/auth/oidc/callback`
- Redis-backed queue implementation:
  - main queue + processed idempotency set + DLQ queue
- Neo4j driver integration:
  - graph node upsert and traversal query service
- LangGraph-style agent runtime skeleton:
  - proposed actions + policy gate + tool adapter execution
- Production hardening additions:
  - dev auth route gating via `APP_ENV`, `ENABLE_DEV_AUTH_ROUTES`, `DISABLE_DEV_AUTH_ROUTES_IN_PROD`
  - LLM timeout + bounded retries + circuit breaker + per-org token budget guardrails
  - deterministic workflow failure contracts for policy/tool failures
  - worker and scheduler service entrypoints under `backend/cmd`
  - graph schema bootstrap + relationship extraction + finance query APIs
  - retrieval eval endpoint with precision/recall/NDCG-style gate output
  - connector adapter routes for ERP/bank/CRM/docs/ticketing/slack
  - field-level ACL checks for sensitive retrieval/workflow fields
  - OpenTelemetry OTLP exporter integration with fallback spans
  - queue lag metrics and OTEL health metric exposure in `/metrics` and `/metrics/prometheus`
  - worker batch endpoint for queue topology drain testing (`/api/v1/ops/worker/run-batch`)
  - identity resolution v2 persisting canonical profiles and aliases in PostgreSQL
  - embedding ingestion worker writing real `documents` and `document_chunks` (pgvector embeddings)
  - CI compile gate + dependency security audit baseline (`scripts/security_audit.py`)
  - OIDC state+nonce validation, PKCE challenge support, token exchange, and API session JWT issuance
