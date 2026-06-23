# M34 — Policy Engine

M34 is the **single enterprise financial governance gate** for the ERP and Finance OS. Every mutation path delegates threshold, SoD, risk, and approval decisions to the unified policy engine — never hardcoded INR tiers in module code.

## Golden rule (non-negotiable)

| Layer | Role |
|-------|------|
| `app/services/policy_service.py` | Legacy ABAC/RBAC helpers — **delegates to governance engine**, no business thresholds |
| `governance_policy_service` + DB rules | **Single source of truth** for thresholds, SoD, fiscal lock, compliance |
| Module `*_policy_engine.py` files | **Thin facades** calling `policy_engine.evaluate()` only |

**Never** add `if amount > X` inside AP, Banking, Treasury, GST, or Agent modules.

## Persistence

Migration `059_policy_engine.sql`:

- `governance.policies` — master policy catalog
- `governance.policy_rules` — extended with `policy_id`, `policy_code` (backward compatible)
- `governance.policy_decisions` — append-only evaluation audit
- `governance.approval_matrix` — configurable INR approval tiers
- `governance.policy_exceptions` — override workflow records

Bootstrap: `python backend/scripts/bootstrap_governance_policies.py --org-id <uuid>`

## Canonical API

`policy_engine.evaluate(org_id, action=..., attrs=..., roles=..., actor_user_id=..., dry_run=...)`

Evaluation order: cache → rules → SoD → risk → approval matrix → persist → events.

HTTP: `/api/v1/governance/policies/evaluate`, `/policies/decisions`, `/policies/approval-matrix`, `/policies/sod`, `/policies/exceptions`

## Action code catalog

| Action | Module |
|--------|--------|
| `journal.post`, `journal.approve`, `journal.reverse` | M10 Journals |
| `period.close` | M12 Fiscal |
| `invoice.approve`, `payment.scheduled` | M11 AP |
| `payment.execute`, `payment.request` | M22 Banking |
| `treasury.transfer`, `treasury.payment` | M24 Treasury |
| `gst.file`, `gst.return.submit` | M19 GST |
| `reconciliation.override` | M23 Reconciliation |
| `agent.recommend`, `agent.execute` | M29 Agents |
| `workflow.approve` | M2 Workflow |
| `forecast.override` | M30 Forecasting |

## Upstream integration checklist

| Module | Integration point | Status |
|--------|-------------------|--------|
| IAM `evaluate_access` | Calls `policy_engine.evaluate()` first | Done |
| M10 Journals | `posting_routes` via `evaluate_access` | Done |
| M22 Banking | `payment_policy_engine` delegates | Done |
| M24 Treasury | `treasury_policy_service`, `transfer_engine` | Done |
| M11 AP / M18 Procurement | `pr_approval_workflow` matrix lookup | Done |
| M19 GST | `filing_routes` via `enforce_tax_action` / IAM | Done |
| M23 Reconciliation | Adjustment approve policy gate | Done |
| M29 Agents | `policy_reasoner`, `context_service` | Done |
| M2 Workflow | `build_approval_chain` matrix feed | Done |
| M33 Audit | `policy.*` events materialized | Done |

## Events

Emitted: `policy.approved`, `policy.denied`, `policy.override.required`, `policy.risk.detected`, `policy.evaluated`

Consumer: `_consume_policy_events` in `event_consumers.py` (M33 materialization + risk logging).

## Redis cache

Keys: `policy:rules:{org_id}`, `policy:matrix:{org_id}` — 60s TTL; invalidate on policy/matrix upsert.
