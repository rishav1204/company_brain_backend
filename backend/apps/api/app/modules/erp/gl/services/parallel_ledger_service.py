from __future__ import annotations

from app.core.config import settings
from app.modules.erp.gl.repositories.parallel_ledger_repository import parallel_ledger_repository
from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository
from app.modules.erp.journals.repositories.journal_repository import journal_repository
from app.modules.erp.security.company_resolution_service import company_resolution_service
from app.modules.erp.security.company_scope import require_company_id_for_erp_write


class ParallelLedgerService:
    def create_ledger(
        self,
        org_id: str,
        *,
        ledger_code: str,
        ledger_name: str,
        accounting_standard: str = "IFRS",
        company_id: str | None = None,
    ) -> dict:
        if settings.erp_require_company_id:
            company_id = company_resolution_service.resolve_for_write(
                org_id, company_id=company_id, operation="gl.parallel_ledger.create"
            )
        elif company_id:
            require_company_id_for_erp_write(
                org_id=org_id, company_id=company_id, operation="gl.parallel_ledger.create"
            )
        return parallel_ledger_repository.create_ledger(
            org_id,
            ledger_code=ledger_code,
            ledger_name=ledger_name,
            accounting_standard=accounting_standard,
            company_id=company_id,
        )

    def get_ledger(self, org_id: str, *, ledger_id: str) -> dict:
        row = parallel_ledger_repository.get_ledger(org_id, ledger_id=ledger_id)
        if not row:
            raise ValueError("Parallel ledger not found")
        return row

    def list_ledgers(self, org_id: str, *, active_only: bool = True) -> list[dict]:
        return parallel_ledger_repository.list_ledgers(org_id, active_only=active_only)

    def mirror_journal(
        self,
        org_id: str,
        *,
        parallel_ledger_id: str,
        journal_id: str,
    ) -> dict:
        ledger = parallel_ledger_repository.get_ledger(org_id, ledger_id=parallel_ledger_id)
        if not ledger:
            raise ValueError("Parallel ledger not found")

        journal = journal_repository.get(org_id, journal_id=journal_id)
        if not journal:
            raise ValueError("Journal not found")
        if str(journal.get("journal_status")) != "posted":
            raise ValueError("Only posted journals can be mirrored to parallel ledger")

        if parallel_ledger_repository.has_entries_for_journal(
            org_id, parallel_ledger_id=parallel_ledger_id, journal_id=journal_id
        ):
            return {
                "parallel_ledger_id": parallel_ledger_id,
                "journal_id": journal_id,
                "idempotent": True,
                "entries": parallel_ledger_repository.list_entries(
                    org_id, parallel_ledger_id=parallel_ledger_id, source_journal_id=journal_id
                ),
            }

        lines = journal_line_repository.list_by_journal(org_id, journal_id=journal_id)
        posting_date = str(journal.get("posting_date") or "")[:10]
        fiscal_period_id = journal.get("fiscal_period_id")
        created: list[dict] = []
        for line in lines:
            entry = parallel_ledger_repository.insert_entry(
                org_id,
                parallel_ledger_id=parallel_ledger_id,
                source_journal_id=journal_id,
                account_id=str(line["account_id"]),
                debit_amount=float(line.get("debit_amount") or 0),
                credit_amount=float(line.get("credit_amount") or 0),
                posting_date=posting_date,
                fiscal_period_id=str(fiscal_period_id) if fiscal_period_id else None,
            )
            created.append(entry)
        return {
            "parallel_ledger_id": parallel_ledger_id,
            "journal_id": journal_id,
            "entries_mirrored": len(created),
            "entries": created,
        }

    def mirror_posted_journals(
        self,
        org_id: str,
        *,
        parallel_ledger_id: str,
        limit: int = 100,
    ) -> dict:
        journals = journal_repository.list(org_id, journal_status="posted", limit=limit)
        mirrored = 0
        skipped = 0
        for journal in journals:
            jid = str(journal["id"])
            if parallel_ledger_repository.has_entries_for_journal(
                org_id, parallel_ledger_id=parallel_ledger_id, journal_id=jid
            ):
                skipped += 1
                continue
            self.mirror_journal(org_id, parallel_ledger_id=parallel_ledger_id, journal_id=jid)
            mirrored += 1
        return {"parallel_ledger_id": parallel_ledger_id, "mirrored": mirrored, "skipped": skipped}

    def list_entries(
        self,
        org_id: str,
        *,
        parallel_ledger_id: str,
        source_journal_id: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        return parallel_ledger_repository.list_entries(
            org_id,
            parallel_ledger_id=parallel_ledger_id,
            source_journal_id=source_journal_id,
            limit=limit,
        )


parallel_ledger_service = ParallelLedgerService()
