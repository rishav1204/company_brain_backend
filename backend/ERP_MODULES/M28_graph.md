# M28 — Operational Graph Engine

## Overview

M28 is the Finance OS **relationship intelligence layer**. It stores entity relationships, dependencies, lineage, and causality in Neo4j while PostgreSQL remains the system of record.

## Architecture

- **Graph store:** Neo4j via platform [`neo4j_service`](../../apps/api/app/services/neo4j_service.py)
- **Bulk projection:** [`graph_extraction_service`](../../apps/api/app/services/graph_extraction_service.py) (legacy + ERP tables)
- **Incremental sync:** `graph_ingestion_pipeline` on ERP domain events
- **Audit only in Postgres:** `finance_os.graph_sync_events` (no graph structure duplication)

## Node types

Vendor, Customer, Invoice, Payment, Journal, GSTReturn, Reconciliation, BankTransaction, Compliance, Asset, Workflow, User, Decision, Incident, KPI, ...

## Relationship types

ISSUED, REQUIRES_APPROVAL, APPROVES, GENERATED, PAID_BY, SETTLED_BY, REPORTED_IN, MATCHED_IN, FILED_AS, BLOCKED_BY, PRECEDES, CAPITALIZED_AS, ...

## API

Base path: `/api/v1/finance-os/graph`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Module health |
| GET | `/entity/{entity_id}` | 1-hop neighbors |
| GET | `/lineage/{entity_id}` | Lifecycle traversal |
| GET | `/dependencies/{entity_id}` | Inbound dependents |
| GET | `/root-cause/{entity_id}` | Causal path explanation |
| GET | `/search` | Entity search |
| GET | `/visualization/{entity_id}` | Nodes/edges JSON |
| POST | `/sync` | Queue entity sync |
| POST | `/rebuild` | Full org rescan |
| POST | `/copilot` | Q&A over graph + memory |

Legacy routes at `/api/v1/graph/*` delegate to M28 services.

## Events

- `graph.updated`
- `graph.lineage.generated`
- `graph.dependency.detected`
- `graph.root_cause.generated`

## Bridges

- **M27 Memory:** causal chain summaries via `memory_bridge`
- **M25 Invoice AI:** vendor ecosystem via dependency traversal
- **M26 Workflow Intel:** bottleneck annotation on Workflow nodes
- **M23/M24:** reconciliation and cash chain lineage
- **Platform retrieval:** real graph traces replace hardcoded stubs
- **LangGraph:** read-only `graph.traverse` tool

## Migration

`053_finance_os_graph_audit.sql` — audit table only

## Backfill

```bash
ORG_ID=<uuid> python backend/scripts/backfill_finance_os_graph.py
```

## Tests

```bash
pytest backend/apps/api/app/modules/finance_os/graph/tests/test_graph_m28.py -q
```
