# M35 — Multi-Entity & Consolidation Engine

M35 is the **enterprise group finance platform** — legal entities, branches, intercompany ledger, elimination journals, and consolidated reporting within a single tenant.

## Golden rule (non-negotiable)

| Do | Don't |
|----|-------|
| Use **`core.companies`** / **`core.branches`** as legal entity + branch source of truth | Create parallel `erp.entities` / `erp.branches` tables |
| Add **`company_id`** + **`branch_id`** via additive migrations | Rewrite AP/AR/GL modules |
| Route consolidated reporting through **M31 + consolidation MVs** | Scan transactional tables at report time |

**Terminology:** Blueprint `entity_id` = ERP column **`company_id`** (FK → `core.companies.id`).

## Persistence

Migration `060_multi_entity_consolidation.sql`:

- Extended `core.companies` (`entity_code`, `is_consolidation_parent`, `consolidation_method`)
- Extended `core.branches` (`gstin`)
- `erp.entity_hierarchy`, `erp.intercompany_transactions`, `erp.intercompany_balances`
- `erp.consolidation_runs`, `erp.elimination_entries`, `erp.ownership_snapshots`
- `company_id` / `branch_id` on journals, ledger, GST, reporting MVs
- `erp_reporting.consolidated_trial_balance_mv`

Bootstrap: `python backend/scripts/bootstrap_consolidation_hierarchy.py --org-id <uuid>`

## Canonical API

`consolidation_engine.run_consolidation(org_id, group_company_id=..., fiscal_period_id=..., dry_run=...)`

Pipeline: validate period close → aggregate entity TB → IC eliminations → ownership → persist consolidated MV → events.

HTTP prefix: `/api/v1/erp/consolidation/*`

## Upstream integration checklist

| Module | Integration | Status |
|--------|-------------|--------|
| M1 IAM | `core.companies` / `core.branches`; `evaluate_branch_scope` | Done |
| M10 Journals | `company_id` list filter; `branch_id` on headers/lines | Done |
| M12 Fiscal | `entity.closed` on period close | Done |
| M22/M24 Treasury | IC auto-register on cross-entity transfer | Done |
| M31 Reporting | `company_id` filter on TB aggregation | Done |
| M33 Audit | `consolidation.*` / `intercompany.*` materialization | Done |
| M34 Policy | `company_id` on approval matrix; `consolidation.run` gate | Done |
| Object context | AP invoice + journal `company_id` resolution | Done |

## Events

Emitted: `consolidation.completed`, `consolidation.requested`, `elimination.generated`, `intercompany.created`, `intercompany.mismatch.detected`, `entity.closed`

Consumer: `_consume_consolidation_events` in `event_consumers.py`.

## v1 non-goals

Multi-currency FX translation (scaffold only in `currency_engine`), unrealized IC inventory profit, separate ERP instance per company.
