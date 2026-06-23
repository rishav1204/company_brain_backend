# M26 — Workflow Intelligence Engine

## Purpose

M26 is the **organizational process intelligence layer** for Finance OS. It observes M2 workflow executions, detects bottlenecks, predicts SLA breaches, scores efficiency, and recommends approval optimizations — **advisory only**, never auto-modifies workflow definitions or auto-approves.

## Schema (`finance_os.*`)

Migration: `backend/migrations/051_finance_os_workflow_intelligence.sql`

| Table | Purpose |
|-------|---------|
| `finance_os.workflow_snapshots` | Completed/running workflow execution summaries |
| `finance_os.workflow_stage_metrics` | Per-stage duration, queue, and approval times |
| `finance_os.workflow_predictions` | SLA completion and breach-risk forecasts |
| `finance_os.workflow_recommendations` | Optimization suggestions (accept/reject audited) |

Also extends `workflow.latency_samples` with `step_key` and `assignee_id`.

## Package

`backend/apps/api/app/modules/finance_os/workflow_intelligence/`

- **Pipeline:** `workflow_intelligence_pipeline.run()` — canonical orchestration
- **Engines:** bottleneck, SLA, workflow graph, optimization, scoring
- **AI:** copilot, SLA predictor, bottleneck detector, optimization advisor, reasoner
- **Retrieval:** workflow_memory (writes via M27 `memory_writer_service`), approval patterns via M27 search
- **Services:** analysis, bottleneck, SLA prediction, approval optimization, patterns, insights

## APIs (`/api/v1/finance-os/workflow-intelligence`)

| Method | Path | Action |
|--------|------|--------|
| GET | `/health` | Org workflow health score |
| GET | `/bottlenecks` | Ranked stage bottlenecks |
| GET | `/sla-risks` | SLA breach risk list |
| GET | `/recommendations` | Open optimization recommendations |
| GET | `/analytics` | Dashboard aggregates |
| POST | `/analyze` | Trigger pipeline |
| GET | `/snapshots/{workflow_instance_id}` | Snapshot record |
| GET | `/predictions` | Predictions for instance |
| POST | `/copilot` | Natural language Q&A |
| POST | `/recommendations/{id}/accept` | Accept recommendation (audit) |
| POST | `/recommendations/{id}/reject` | Reject recommendation (audit) |
| POST | `/override-prediction` | Manual SLA override (audit) |

Legacy: `GET /workflows/metrics/summary` includes `workflow_intelligence_health`.

## Pipeline flow

```
M2 workflow events (completed, stage.completed, approval.*, sla.breached)
  → workflow_intelligence_pipeline.run(instance_id)
    → ingest snapshot + stage metrics from workflow.*
    → bottleneck + SLA + optimization engines
    → persist finance_os.*
  → emit workflow.bottleneck.detected, workflow.sla_risk.detected, etc.
```

## Efficiency bands

| Score | Band |
|-------|------|
| >90 | excellent |
| 70–90 | good |
| 50–70 | needs_review |
| <50 | poor |

## Events

**Emitted:** `workflow.bottleneck.detected`, `workflow.sla_risk.detected`, `workflow.optimization.recommended`, `workflow.health.updated`, `workflow.intelligence.completed`

**Consumed:** `workflow.completed`, `workflow.failed`, `workflow.stage.completed`, `approval.completed`, `sla.breached`

**M2 additions:** `workflow.stage.entered`, `workflow.stage.completed`, `workflow.approved` (alias on approval)

## Cross-module value

| Module | Workflow keys analyzed |
|--------|------------------------|
| M11 AP | `AP_INVOICE_APPROVAL` |
| M12 AR | `AR_INVOICE_APPROVAL`, `AR_WRITE_OFF_APPROVAL` |
| M15 Procurement | `PR_APPROVAL`, `PO_APPROVAL`, `GRN_CONFIRMATION` |
| M16 Expenses | `EXPENSE_CLAIM_APPROVAL`, `EXPENSE_REIMBURSEMENT` |
| M21 Compliance | `PERIOD_CLOSE`, filing workflows |
| M22/M24 | `PAYMENT_APPROVAL`, `TREASURY_PAYMENT_APPROVAL` |
| M27 Memory | `write_pattern_memory` and approval pattern reads via canonical memory layer |

## Backfill

`python backend/scripts/backfill_workflow_intelligence.py --dsn <DSN> --org-id <ORG> --days 30`

## Tests

`finance_os/workflow_intelligence/tests/test_workflow_intelligence_m26.py` — 55+ unit tests.
