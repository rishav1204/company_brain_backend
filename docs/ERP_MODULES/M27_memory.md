# M27 — Enterprise Financial Memory System

## Overview

M27 is the canonical Finance OS organizational memory layer. It stores **compressed knowledge** (not raw events) with importance gating, semantic embeddings, ranked retrieval, summarization, and lifecycle decay.

## Architecture

- **Canonical storage:** `finance_os.memory_entries`, `finance_os.memory_embeddings`, `finance_os.memory_references`
- **Compatibility projection:** slim rows in platform `memory_records` for legacy hybrid retrieval
- **Single write path:** `memory_writer_service.write()`
- **Ingestion:** `memory_ingestion_pipeline.run_from_event()` on meaningful domain events

## API

Base path: `/api/v1/finance-os/memory`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Module health |
| GET | `/search` | Semantic memory search |
| GET | `/entity/{entity_type}/{entity_id}` | Entity memories |
| GET | `/summary` | Org summary by category |
| GET | `/insights` | Patterns and risk signals |
| POST | `/write` | Manual knowledge entry |
| POST | `/rebuild` | Backfill historical memories |
| POST | `/copilot` | Q&A over memories |
| GET | `/references/{memory_id}` | Source references |
| POST | `/admin/decay/run` | Trigger TTL cleanup |
| POST | `/admin/summarize` | Summarize entity memories |
| PATCH | `/entries/{id}` | Manual correction |
| DELETE | `/entries/{id}` | Soft archive |

## Importance gating

| Band | Score | Default TTL |
|------|-------|-------------|
| Critical | 90+ | forever |
| High | 70–89 | 180d |
| Medium | 50–69 | 90d |
| Low | <50 | discarded |

## Events

- `memory.created`
- `memory.updated`
- `memory.expired`
- `memory.high_importance.detected`
- `memory.summarized`

## Bridges

- **M25 Invoice AI:** vendor/accounting retrieval via M27 search; writes on prediction override, duplicate, anomaly
- **M26 Workflow Intelligence:** fixed `write_pattern_memory`; approval pattern reads via M27
- **M23 Reconciliation:** `reconciliation_bridge.reconciliation_context()`
- **M24 Treasury:** `treasury_bridge.treasury_context()`
- **Platform agents:** read-only `memory.search` tool in langgraph runner
- **M28 Graph:** causal chain summaries written when root-cause detected; graph copilot combines graph + memory context

## Migration

`052_finance_os_memory_system.sql`

## Backfill

```bash
ORG_ID=<uuid> python backend/scripts/backfill_finance_os_memory.py
```

## Tests

```bash
pytest backend/apps/api/app/modules/finance_os/memory/tests/test_memory_m27.py -q
```
