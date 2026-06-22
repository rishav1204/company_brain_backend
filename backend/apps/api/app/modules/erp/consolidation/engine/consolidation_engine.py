from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.erp.consolidation.engine import (
    currency_engine,
    elimination_engine,
    ownership_engine,
    reporting_engine,
)
from app.modules.erp.consolidation.repositories.consolidation_run_repository import consolidation_run_repository
from app.modules.erp.consolidation.repositories.elimination_repository import elimination_repository
from app.modules.erp.consolidation.repositories.hierarchy_repository import hierarchy_repository
from app.modules.erp.consolidation.repositories.intercompany_repository import intercompany_repository
from app.modules.erp.consolidation.repositories.ownership_snapshot_repository import ownership_snapshot_repository


@dataclass
class ConsolidationResult:
    run_id: str
    status: str
    eliminations: list[dict] = field(default_factory=list)
    consolidated_rows: int = 0
    ownership_snapshots: list[dict] = field(default_factory=list)
    error: str | None = None


def _validate_periods_closed(org_id: str, company_ids: list[str], fiscal_period_id: str) -> str | None:
    closed_statuses = {"closed", "locked", "hard_locked"}
    try:
        from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository

        base = fiscal_period_repository.get(org_id, period_id=fiscal_period_id)
        if not base:
            return None
        period_name = base.get("period_name")
        for cid in company_ids:
            if str(base.get("company_id") or "") in {"", str(cid)}:
                if str(base.get("status") or "").lower() not in closed_statuses:
                    return f"Fiscal period not closed for company {cid}"
                continue
            periods = fiscal_period_repository.list(org_id, company_id=cid)
            match = next((p for p in periods if p.get("period_name") == period_name), None)
            if match and str(match.get("status") or "").lower() not in closed_statuses:
                return f"Fiscal period not closed for company {cid}"
    except Exception:
        pass
    return None


def run_consolidation(
    org_id: str,
    *,
    group_company_id: str,
    fiscal_period_id: str,
    company_ids: list[str] | None = None,
    actor_user_id: str | None = None,
    dry_run: bool = False,
) -> ConsolidationResult:
    if not hierarchy_repository.schema_ready():
        return ConsolidationResult(run_id="", status="failed", error="consolidation_schema_not_ready")

    if company_ids is None:
        children = hierarchy_repository.list_children(org_id, group_company_id)
        company_ids = [group_company_id] + [c["child_company_id"] for c in children]
    company_ids = list(dict.fromkeys(company_ids))

    if not dry_run:
        period_err = _validate_periods_closed(org_id, company_ids, fiscal_period_id)
        if period_err:
            return ConsolidationResult(run_id="", status="failed", error=period_err)

    run = {"id": "dry-run"} if dry_run else consolidation_run_repository.create(
        org_id,
        group_company_id=group_company_id,
        fiscal_period_id=fiscal_period_id,
        company_ids=company_ids,
        started_by=actor_user_id,
    )
    run_id = str(run["id"])

    try:
        entity_tbs = [
            reporting_engine.aggregate_entity_trial_balance(
                org_id, fiscal_period_id=fiscal_period_id, company_id=cid
            )
            for cid in company_ids
        ]
        merged = reporting_engine.merge_trial_balances(entity_tbs)

        ic_balances = intercompany_repository.list_balances(org_id)
        ic_txs = intercompany_repository.list_transactions(org_id, status="matched")
        elim_lines = elimination_engine.build_ic_eliminations(ic_balances)
        elim_lines.extend(elimination_engine.build_ic_transaction_eliminations(ic_txs))

        hierarchy = hierarchy_repository.list_for_org(org_id)
        ownership_snaps: list[dict] = []
        tb_by_company = dict(zip(company_ids, entity_tbs))
        for cid in company_ids:
            if cid == group_company_id:
                continue
            pct = 100.0
            for h in hierarchy:
                if h.get("child_company_id") == cid and h.get("parent_company_id") == group_company_id:
                    pct = float(h.get("ownership_percent") or 100)
            profit = sum(float(r.get("balance") or 0) for r in tb_by_company.get(cid, []))
            split = ownership_engine.compute_ownership_split(subsidiary_profit=profit, ownership_percent=pct)
            ownership_snaps.append({"company_id": cid, "subsidiary_profit": profit, **split})

        if not dry_run:
            for line in elim_lines:
                elimination_repository.record(org_id, consolidation_run_id=run_id, **line)
            for snap in ownership_snaps:
                ownership_snapshot_repository.record(
                    org_id,
                    consolidation_run_id=run_id,
                    subsidiary_company_id=snap["company_id"],
                    ownership_percent=snap["ownership_percent"],
                    subsidiary_profit=snap["subsidiary_profit"],
                    parent_share=snap["parent_share"],
                    minority_interest=snap["minority_interest"],
                )
            row_count = reporting_engine.persist_consolidated_trial_balance(
                org_id,
                consolidation_run_id=run_id,
                group_company_id=group_company_id,
                fiscal_period_id=fiscal_period_id,
                rows=merged,
            )
            consolidation_run_repository.update_status(org_id, run_id, status="completed")
            from app.modules.erp.consolidation.events import consolidation_events

            consolidation_events.emit_completed(org_id, run_id=run_id)
        else:
            row_count = len(merged)

        return ConsolidationResult(
            run_id=run_id,
            status="completed" if not dry_run else "dry_run",
            eliminations=elim_lines,
            consolidated_rows=row_count,
            ownership_snapshots=ownership_snaps,
        )
    except Exception as exc:
        if not dry_run and run_id != "dry-run":
            consolidation_run_repository.update_status(org_id, run_id, status="failed", error_message=str(exc))
        return ConsolidationResult(run_id=run_id, status="failed", error=str(exc))
