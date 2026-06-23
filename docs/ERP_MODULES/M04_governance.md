# Module 4 — Audit, Compliance & Governance Core

**Audience:** Backend, compliance, workflow, and platform teams  
**Base URL:** `http://localhost:8000/api/v1`  
**Status:** v1.1 — enterprise trust layer (migrations `016`, `017` after `015` platform events)

---

## Purpose

Module 4 is the **enterprise trust backbone** of the Finance OS. Nothing important happens silently:

- Every mutation is **traceable**, **attributable**, and **auditable**
- Policies enforce **maker-checker**, fiscal locks, and approval limits
- AI decisions store **summaries + hashes** — never raw chain-of-thought
- Compliance events track GST/TDS and approval trails
- Module 3 (event replay, retries, DLQ) is **forensically explainable** only with M4

---

## Architecture

```text
HTTP Request
  → GovernanceTraceMiddleware (trace_id, request_id)
  → RequestMiddleware (auth org)
  → AuditCaptureMiddleware (mutations)
  → Business action
  → platform_event_service.publish (optional)
  → audit.persist queue OR audit_service.record
  → immutable audit_logs + governance/compliance tables
```

**Reuse (do not duplicate):** OTEL (`trace.py`), IAM `evaluate_access`, M03 event bus, M02 workflow realtime hub.

---

## Database — migration `016`

| Schema | Table | Purpose |
|--------|-------|---------|
| `public.audit_logs` | extended columns | Immutable operational history (append-only triggers from `001`) |
| `audit.audit_logs` | VIEW | Namespace alias over `public.audit_logs` |
| `audit.ai_reasoning_traces` | AI explainability | prompt_hash, summary, confidence, decision |
| `audit.evidence_links` | Evidence chain | invoice ↔ approval ↔ AI trace |
| `governance.policy_rules` | Policy engine | maker-checker, thresholds, fiscal |
| `governance.violations` | Violations | open/resolved, append-only delete |
| `governance.retention_policies` | Retention | 8-year default (India finance) |
| `compliance.compliance_events` | Compliance | GST, TDS, policy alerts |

---

## Module layout

```text
modules/platform/governance/
  routes/       audit, compliance, governance, policies, evidence
  services/     audit, policy, governance, compliance, ai_trace, evidence, retention, risk
  repositories/ audit, policy, compliance, violations, evidence, ai_trace
  middleware/   trace, audit capture, governance enforcement
  events/       audit.log.created, policy.violation.detected, compliance.alert.generated
  explainability/  ai_reasoning_tracker, evidence_linker
  retention/    rules, archival (no hard-delete)
  tests/
```

---

## API surface

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/audit/logs` | Filtered immutable audit log |
| `GET` | `/audit/timeline/{entity_type}/{entity_id}` | Entity timeline |
| `GET` | `/audit/export` | JSON export |
| `GET` | `/audit/evidence/{entity_type}/{entity_id}` | Evidence links |
| `POST` | `/audit/evidence/link` | Link evidence |
| `POST` | `/audit/ai-traces` | Record AI reasoning trace |
| `GET` | `/audit/ai-traces/{id}` | Retrieve trace |
| `GET` | `/compliance/events` | Compliance event list |
| `POST` | `/compliance/gst/filed` | Record GST filing |
| `GET` | `/governance/violations` | Open violations |
| `POST` | `/governance/violations/{id}/resolve` | Resolve violation |
| `POST` | `/governance/evaluate` | Policy evaluation |
| `POST` | `/governance/risk/payment` | Payment risk assessment |
| `GET` | `/policies` | List policy rules |
| `POST` | `/policies` | Upsert policy (governance_admin) |
| `POST` | `/policies/simulate` | Dry-run policy |

---

## Maker-checker (India)

Platform policy `maker_checker_required` + IAM `enforce_maker_checker`:

- Creator cannot approve own invoice, payment, journal, GST filing, or reconciliation

---

## Event integration (M03)

| Event | Owner | When |
|-------|-------|------|
| `audit.log.created` | governance.audit | After audit record |
| `policy.violation.detected` | governance.engine | Policy block |
| `compliance.alert.generated` | governance.compliance | Compliance record |

Consumers: `audit.persist` → `audit_service`; violations/alerts → M02 realtime hub.

Queue failures: `queue_manager._emit_system_failure` writes forensic audit entry.

---

## AI governance

- Store: `prompt_hash`, `reasoning_summary`, `confidence_score`, `retrieved_context` refs
- Never store raw chain-of-thought
- Agent runs (`agent.run` consumer) auto-record `ai_trace`

---

## Retention

- Default **8 years** for audit, GST, financial records
- **Archival only** — `purge_scheduler` never hard-deletes audit data

---

## Tests

```powershell
cd backend\apps\api
python -m pytest app/modules/platform/governance/tests tests/test_governance_maker_checker.py -q
```

---

## v1.1 closure (gap fixes)

| Area | Fix |
|------|-----|
| JWT audit | Middleware reads `get_request_context()` after handler |
| Dedupe | `skip_auto_audit()` when `audit_service.record()` runs |
| Physical `audit.audit_logs` | Migration `017` + sync trigger from `public.audit_logs` |
| Replay audit | `record_replay()` + evidence links |
| Webhook audit | Delivery success/fail logged |
| Retry audit | Per-attempt `queue.retry.scheduled` audit |
| Workflow governance | Approval path runs policy + duplicate payment check |
| TDS/GST | Extended compliance APIs |
| Forensics | `/governance/forensics/*` + metrics endpoint |
| RBAC | `auditor` read-only; `governance_admin` for policy writes |
| Metrics | Governance counters on `/metrics` and `/governance/metrics` |
| Retrieval trace | `retrieval_trace_manager` wired in `/query/context` |
| Field crypto | Optional `GOVERNANCE_FIELD_ENCRYPTION_KEY` or hash fallback |

## Apply migrations

```powershell
psql $POSTGRES_DSN -f backend/migrations/016_governance_core.sql
psql $POSTGRES_DSN -f backend/migrations/017_audit_physical_table.sql
```

---

## Dependencies

| Module | Integration |
|--------|-------------|
| M01 IAM | `evaluate_access`, maker-checker, roles |
| M02 Workflow | `audit_transition`, approval authority, realtime |
| M03 Events | audit.persist, governance events, DLQ forensics |
| M05+ ERP | Emit + audit on write paths (helpers ready) |
