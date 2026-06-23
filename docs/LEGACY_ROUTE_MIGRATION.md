# Legacy API Route Migration Plan

**Status:** Active (Phase A + B complete; Phase C pending sunset)  
**Sunset date:** 2026-12-31  
**Owner:** Platform API  

## Purpose

`app/api/routes/` contains the original Finance OS v1 surface. New code lives under `app/modules/` with clearer domain boundaries. Both stacks are mounted today; this document defines the migration path to modular routes only.

## Middleware

`app/legacy_deprecation_middleware.py` adds `Deprecation`, `Sunset`, and `Link` headers to responses from legacy intelligence and workflow paths under `/api/v1`.

Successor mapping examples:

| Legacy path | `Link` successor |
|-------------|------------------|
| `/agents/run` | `/finance-os/agents/run` |
| `/graph/*` | `/finance-os/graph/*` |
| `/decisions`, `/memory` | `/finance-os/memory` |
| `/memory/decay/run` | `/finance-os/memory/admin/decay/run` |
| `/workflows` | `/workflows/definitions` |
| `/workflows/{id}/actions` | `/approvals` |
| `/auth/password/login` | `/auth/login` |

## Route mapping

| Legacy route module | Example legacy path | Modular successor | Notes |
|--------------------|---------------------|-------------------|-------|
| `auth.py` | `/api/v1/auth/password/login` | `/api/v1/auth/login` (IAM) | Dev routes gated by `ENABLE_DEV_AUTH_ROUTES` |
| `workflows.py` | `/api/v1/workflows` | `/api/v1/workflows/definitions`, `/workflows/start` | v2 routes add definitions, tasks, escalations |
| `agents.py` | `/api/v1/agents/run` | `/api/v1/finance-os/agents/*` | LangGraph runner shared |
| `graph.py` | `/api/v1/graph/*` | `/api/v1/finance-os/graph/*` | Neo4j + Postgres graph |
| `decisions_memory.py` | `/api/v1/decisions`, `/api/v1/memory` | `/api/v1/finance-os/memory/*` | Operational memory |
| `memory_admin.py` | `/api/v1/memory/decay/run` | `/api/v1/finance-os/memory/admin/decay/run` | Admin ops |
| `ingestion.py` | `/api/v1/ingestion/*` | `platform/documents` (partial) | Ingestion pipeline remains legacy until DMS unification |
| `retrieval.py` | `/api/v1/query/context` | — | Retrieval eval stack; no modular duplicate yet |
| `sources.py` | `/api/v1/sources/*` | — | Connector source registry |
| `queue.py` | `/api/v1/queue/*` | `platform/events` workers | Ops endpoints |
| `platform_events.py` | `/api/v1/platform/events/*` | `platform/events` | Event bus admin |
| `connectors.py` | `/api/v1/connectors/*` | `platform/integrations` | CDC connectors |
| `companies.py` | `/api/v1/companies/*` | `core/iam` organizations | Demo in-memory company APIs |

## ERP module legacy aliases (2026-06)

These canonical modular prefixes also mount shorter legacy aliases (no sunset in 2026-12 batch):

| Legacy alias | Canonical prefix | Module |
|--------------|------------------|--------|
| `/api/v1/banking/*` | `/api/v1/erp/banking/*` | M22 Banking |
| `/api/v1/treasury/*` | `/api/v1/erp/treasury/*` | M24 Treasury |
| `/api/v1/banking/reconciliation/*` | `/api/v1/erp/reconciliation/*` | M23 Reconciliation |

## Compliance route alignment (2026-06)

| Path | Module | Purpose |
|------|--------|---------|
| `/api/v1/compliance/*` | `erp/compliance` (M21) | Compliance calendar, obligations |
| `/api/v1/erp/compliance/*` | `erp/compliance` (M21) | Canonical prefix |
| `/api/v1/tax/compliance/*` | `erp/tax` | GST/TDS tax compliance calendar & copilot |

## Fiscal period alignment (2026-06)

| Deprecated | Canonical |
|------------|-----------|
| `/api/v1/erp/fiscal-periods/*` (GL router, unmounted) | `/api/v1/erp/ledger/periods/*` |

M12 fiscal module code lives under `modules/erp/fiscal/`; the HTTP prefix is `/erp/ledger` (not `/erp/fiscal`). GL router no longer mounts fiscal period routes.

## Migration phases

### Phase A — Now (2026 Q2) ✅

- [x] Deprecation headers on legacy intelligence routes
- [x] Modular routes are the documented contract in `ERP_MASTER_MODULE_MAP.md`
- [x] New clients must use `/finance-os/*`, `/erp/*`, and `modules/core/iam` paths

### Phase B — 2026 Q3 ✅

- [x] `api/openapi.yaml` marks legacy intelligence/workflow paths `deprecated: true`
- [x] `tests/test_legacy_route_migration.py` asserts modular paths and deprecation headers

### Phase C — 2026 Q4 (sunset)

- [ ] Remove legacy route modules from `main.py`
- [ ] Delete `app/api/routes/agents.py`, `graph.py`, `decisions_memory.py`, duplicate `workflows.py`
- [ ] Keep ops/ingestion/retrieval until platform equivalents exist

## Client action items

1. Switch agent calls from `/agents/*` to `/finance-os/agents/*`
2. Switch graph calls from `/graph/*` to `/finance-os/graph/*`
3. Switch memory/decisions from `/decisions` and `/memory` to `/finance-os/memory/*`
4. Use IAM `/auth/login` instead of `/auth/password/login` when `IAM_USE_DB_AUTH=true`
5. Use `/tax/compliance/*` for tax calendar; `/compliance/*` or `/erp/compliance/*` for M21 calendar
6. Use `/erp/banking/*`, `/erp/treasury/*`, `/erp/reconciliation/*` instead of legacy ERP aliases when building new integrations
