from __future__ import annotations

from app.modules.erp.fiscal.events.year_end_events import emit_fiscal_year_closed, emit_year_end_completed
from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository, year_end_repository
from app.modules.erp.fiscal.repositories.fiscal_year_repository import fiscal_year_repository
from app.modules.erp.fiscal.services.fiscal_year_service import fiscal_year_service
from app.modules.erp.fiscal.validators.year_end_validator import validate_year_end_ready


class YearEndService:
    def run_year_end(
        self,
        org_id: str,
        *,
        fiscal_year_id: str,
        run_by: str,
        retained_earnings_account_id: str | None = None,
    ) -> dict:
        validate_year_end_ready(org_id, fiscal_year_id=fiscal_year_id)
        run = year_end_repository.create(org_id, fiscal_year_id=fiscal_year_id, run_by=run_by)
        fy = fiscal_year_repository.get(org_id, fiscal_year_id=fiscal_year_id) or {}
        journal_id, batch_id = self._generate_closing_journal(
            org_id,
            fiscal_year_id=fiscal_year_id,
            retained_earnings_account_id=retained_earnings_account_id,
            run_by=run_by,
            end_date=str(fy.get("end_date") or ""),
        )
        next_fy = fiscal_year_service.create_fiscal_year(
            org_id,
            start_date=self._next_fy_start(str(fy.get("end_date") or "")),
            end_date=self._next_fy_end(str(fy.get("end_date") or "")),
            set_current=True,
        )
        fiscal_year_repository.set_status(org_id, fiscal_year_id=fiscal_year_id, status="closed")
        completed = year_end_repository.complete(
            org_id,
            run_id=str(run["id"]),
            closing_journal_id=journal_id,
            closing_batch_id=batch_id,
            next_fiscal_year_id=str(next_fy.get("id")),
        )
        emit_fiscal_year_closed(org_id, fiscal_year_id=fiscal_year_id)
        emit_year_end_completed(org_id, run_id=str(run["id"]), fiscal_year_id=fiscal_year_id)
        self._audit(org_id, fiscal_year_id=fiscal_year_id, actor_id=run_by)
        return {"run": completed, "next_fiscal_year": next_fy, "closing_journal_id": journal_id}

    def _next_fy_start(self, end_date: str) -> str:
        y, m, d = [int(x) for x in end_date[:10].split("-")]
        return f"{y}-04-01" if m == 3 else f"{y + 1}-04-01"

    def _next_fy_end(self, end_date: str) -> str:
        y, m, _ = [int(x) for x in end_date[:10].split("-")]
        return f"{y + 1}-03-31" if m == 3 else f"{y + 2}-03-31"

    def _generate_closing_journal(
        self,
        org_id: str,
        *,
        fiscal_year_id: str,
        retained_earnings_account_id: str | None,
        run_by: str,
        end_date: str,
    ) -> tuple[str | None, str | None]:
        periods = fiscal_period_repository.list(org_id, fiscal_year_id=fiscal_year_id, limit=20)
        if not periods:
            return None, None
        last_period_id = periods[0]["id"] if periods else None
        try:
            from app.modules.erp.coa.repositories.account_group_repository import account_group_repository
            from app.modules.erp.coa.repositories.account_repository import account_repository
            from app.modules.erp.journals.services.journal_service import journal_service
            from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator

            groups = account_group_repository.list(org_id, limit=500)
            pl_types = {"income", "expense", "revenue", "cost"}
            pl_accounts = []
            for acc in account_repository.list(org_id, limit=500):
                gid = acc.get("account_group_id")
                grp = next((g for g in groups if str(g.get("id")) == str(gid)), None)
                if grp and str(grp.get("group_type", "")).lower() in pl_types:
                    pl_accounts.append(acc)
            if not pl_accounts:
                return None, None
            lines = []
            net = 0.0
            for acc in pl_accounts:
                aid = str(acc["id"])
                bal = float(acc.get("metadata", {}).get("closing_balance", 0) if isinstance(acc.get("metadata"), dict) else 0)
                if abs(bal) < 0.01:
                    continue
                nature = str(acc.get("nature") or "debit").lower()
                if nature == "credit":
                    lines.append({"account_id": aid, "debit_amount": bal, "credit_amount": 0, "description": "Year-end close"})
                    net += bal
                else:
                    lines.append({"account_id": aid, "debit_amount": 0, "credit_amount": bal, "description": "Year-end close"})
                    net -= bal
            if not lines:
                return None, None
            re_account = retained_earnings_account_id
            if not re_account:
                equity = next((a for a in account_repository.list(org_id, limit=500) if "retained" in str(a.get("account_name", "")).lower()), None)
                re_account = str(equity["id"]) if equity else None
            if not re_account:
                return None, None
            if net >= 0:
                lines.append({"account_id": re_account, "debit_amount": 0, "credit_amount": abs(net), "description": "Retained earnings"})
            else:
                lines.append({"account_id": re_account, "debit_amount": abs(net), "credit_amount": 0, "description": "Retained earnings"})
            journal = journal_service.create(
                org_id,
                journal_type="adjustment",
                posting_date=end_date[:10],
                description="Year-end closing entry",
                lines=lines,
                created_by=run_by,
                idempotency_key=f"year-end:{fiscal_year_id}",
            )
            jid = str(journal.get("id") or journal.get("journal_id") or "")
            from app.modules.erp.journals.services.approval_service import approval_service

            approval_service.approve(org_id, journal_id=jid, approver_id=run_by, skip_maker_checker=True)
            result = posting_orchestrator.post_journal(org_id, journal_id=jid, posted_by=run_by)
            return jid, str(result.get("batch_id") or result.get("ledger_batch_id") or "")
        except Exception:
            return None, None

    def _audit(self, org_id: str, *, fiscal_year_id: str, actor_id: str) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id,
                action="fiscal.year_end.completed",
                object_ref=f"erp:fiscal_year:{fiscal_year_id}",
                entity_type="fiscal_year",
                entity_id=fiscal_year_id,
                source_service="erp.fiscal",
            )
        except Exception:
            pass


year_end_service = YearEndService()
