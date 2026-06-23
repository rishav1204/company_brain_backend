# Module 21 — Compliance Calendar & Regulatory Obligation Engine

Standalone compliance command center: rule-driven due dates, obligations lifecycle, reminders, escalations, penalties, dashboard, and AI readiness — without duplicating GST/TDS filing logic (M19/M20 execute filings; M21 tracks obligations).

**Migration:** `046_erp_compliance_engine.sql`  
**Package:** `backend/apps/api/app/modules/erp/compliance/`

## API

Primary prefix: **`/api/v1/erp/compliance/*`**

Backward-compatible aliases (deprecated): **`/api/v1/compliance/*`** (calendar, risk, copilot via tax router facade)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/calendar` | List obligations (optional `year`/`month` for month view) |
| GET | `/calendar/upcoming` | Upcoming within N days |
| POST | `/calendar/seed` | Generate obligations for period |
| GET | `/obligations` | Filter by status, priority, date range |
| POST | `/obligations` | Create custom obligation |
| PATCH | `/obligations/{id}` | Update assignee, priority, due date (audited) |
| POST | `/complete` | Mark completed → `compliance.completed` |
| POST | `/waive` | Waive with reason (audited) |
| GET | `/dashboard` | Today, upcoming, overdue, escalations, penalty exposure |
| GET/POST | `/rules` | List / upsert org compliance rules |
| POST | `/rules/seed` | Seed India-default rules |
| GET | `/types` | Global compliance type catalog |
| GET | `/risk` | Risk flags + notice predictor |
| GET | `/readiness` | Filing readiness score (GST + TDS aggregate) |
| POST | `/copilot` | Compliance assistant Q&A |
| POST | `/penalties/{id}/override` | Manual penalty override (CFO) |

## Data model

| Table | Purpose |
|-------|---------|
| `erp.compliance_types` | Master definitions (GST_GSTR1, TDS_26Q, PF_RETURN, …) |
| `erp.compliance_rules` | Org-scoped rule engine (due_day, month_offset, frequency, reminders, escalation) |
| `erp.compliance_obligations` | Canonical obligation instances |
| `erp.compliance_reminders` | Scheduled reminder rows |
| `erp.compliance_escalations` | Escalation history L1–L4 |
| `erp.compliance_penalties` | Penalty/interest exposure (stub formulas + manual override) |

Legacy `erp.compliance_calendar` rows migrated into `compliance_obligations` on migration 046.

## Rule schema (metadata / columns)

```json
{
  "frequency": "monthly",
  "due_day": 11,
  "month_offset": 1,
  "reminder_offsets_days": [30, 15, 7, 3, 1],
  "escalation_levels": ["assignee", "manager", "finance_head", "cfo"],
  "regulator": "GSTN",
  "source_module": "M19"
}
```

India-default rules seeded for benchmark org: GSTR-1 (11th), GSTR-3B (20th), GST Payment (20th), TDS Challan (7th), TDS 26Q (quarterly), Internal Audit (annual).

## Events

**Emitted:** `compliance.due`, `compliance.overdue`, `compliance.completed`, `compliance.escalated`, `compliance.obligation.created`

**Consumed / integrated:**
- GST return filed → `complete_by_source(GST_GSTR1|GST_GSTR3B)`
- TDS return filed → `complete_by_source(TDS_26Q|TDS_27Q)`
- TDS challan paid → `complete_by_source(TDS_CHALLAN)`
- Treasury tax payment → `complete_by_source(GST_PAYMENT)`
- `compliance.completed` → fiscal checklist `compliance_obligations_complete`, `tds_returns_filed`
- `scheduler.compliance.daily` → generate + refresh + remind + escalate

## Workflows

- `COMPLIANCE_ESCALATION` — L3+ overdue obligations
- `COMPLIANCE_WAIVE` — waive approval (optional)

## Fiscal close gate

M12 close validator blocks period close when critical/high overdue obligations exist. Checklist adds `compliance_obligations_complete` and `tds_returns_filed`.

## AI (heuristic)

- `compliance_assistant` — natural language calendar queries
- `risk_detector` — overdue, escalations, repeated delays
- `filing_advisor` — readiness score from M19/M20 data
- `notice_predictor` — stub high-risk pattern flags

## IAM

Roles: `compliance_officer`, `tax_manager`, `finance_manager`, `cfo`, `auditor` (read-only)

## Blueprint compliance

| Item | Status |
|------|--------|
| Rule-driven due dates (no hardcoding) | ✅ |
| Obligations CRUD + complete/waive | ✅ |
| Reminders + daily scheduler | ✅ |
| Escalations L1–L4 + workflow | ✅ |
| Penalty architecture (stub formulas) | ✅ |
| GST/TDS/Fiscal/Treasury integration | ✅ |
| Dashboard + readiness API | ✅ |
| PF/ESI/ROC types (stub until partners) | ✅ types only |
| M31 reporting bridge | Dashboard API ready |

**Compliance: ~95%** — penalty legal templates and PF/ESI/ROC filing connectors remain stub/future.
