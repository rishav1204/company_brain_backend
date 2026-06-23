# M33 — Audit Explorer

M33 is the **enterprise trust and explainability layer** of Finance OS. It materializes unified audit timelines, evidence links, and AI decision trails while reusing the canonical governance audit infrastructure.

## Golden rule (non-negotiable)

Audit Explorer GET endpoints read **primarily from `finance_audit.*`**. The canonical immutable audit record remains `audit_logs` / `audit.ai_reasoning_traces` / `audit.evidence_links` via M4 `audit_service` — **never duplicate or replace**.

## M4 vs M33

| Layer | Question | Source |
|-------|----------|--------|
| M4 Governance | What was logged immutably? | `audit_logs`, `audit.ai_reasoning_traces`, `audit.evidence_links` |
| M33 Audit Explorer | Full explainable story for a finance object? | `finance_audit.*` + read-model federation |

## Upstream delegation (do not duplicate)

| Upstream | Integration |
|----------|-------------|
| M4 Governance | `audit_service`, `evidence_service`, `ai_trace_service` |
| M2 Workflow | `approval_repository.list_for_instance`, `workflow_step_repository` |
| M26 Workflow Intelligence | SLA/bottleneck context on workflow traces |
| M27 Memory | Entity-scoped memory in AI explainability |
| M28 Graph | Lineage endpoint and copilot tools |
| M29 Agents | `agent_executions`, `agent_recommendations`, AI trace hook on recommendation |

## Persistence

Migration `058_finance_audit_explorer.sql`:

- `finance_audit.audit_timelines`
- `finance_audit.audit_evidence`
- `finance_audit.ai_decision_trails`

All tables are append-only with RLS. Retention inherits `governance.retention_policies` (8 years default).

## AI safety rule

Never store full LLM prompts or chain-of-thought in `finance_audit.*`. Store reasoning summaries, confidence scores, decision factors, and evidence references only. Prompts are hashed in `audit.ai_reasoning_traces` via M4.

## API prefix

`/api/v1/finance-os/audit/*`

| Endpoint | Purpose |
|----------|---------|
| GET `/timeline/{object_type}/{object_id}` | Object-centric audit timeline |
| GET `/search` | Cross-system audit search |
| GET `/evidence/{object_type}/{object_id}` | Evidence chain |
| GET `/approval-chain/{workflow_id}` | Approval chain explorer |
| GET `/ai-decision/{execution_id}` | AI decision trail |
| GET `/explore/{object_type}/{object_id}` | Unified explore view |
| GET `/lineage/{object_type}/{object_id}` | Entity lineage (M28 facade) |
| POST `/copilot/ask` | Audit copilot |
| POST `/refresh/{object_type}/{object_id}` | On-demand materialization |

## Events

**Emitted:** `audit.timeline.updated`, `audit.evidence.linked`, `audit.ai_decision.recorded`

**Consumed (debounced):** `audit.log.created`, invoice/journal/workflow/agent/forecast/payment/reconciliation/gst/report domain events

## Bootstrap

```bash
python backend/scripts/bootstrap_finance_audit.py --org-id <uuid> --limit 5000
```
