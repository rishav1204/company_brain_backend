from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.banking.repositories.bank_account_repository import bank_account_repository
from app.modules.erp.banking.repositories.bank_transaction_repository import bank_transaction_repository
from app.modules.erp.treasury.engine.cash_engine import build_account_snapshot, build_position
from app.modules.erp.treasury.events.treasury_events import emit_cash_position_updated
from app.modules.erp.treasury.repositories.cash_position_repository import cash_position_repository
from app.modules.erp.treasury.repositories.payment_request_repository import payment_request_repository


class CashPositionService:
    def compute_live_position(self, org_id: str) -> dict:
        acct_list = bank_account_repository.list(org_id, active_only=True)
        account_ids = [str(acct["id"]) for acct in acct_list]
        sums_by_account = bank_transaction_repository.sum_by_accounts(
            org_id, bank_account_ids=account_ids, reconciled_only=True
        )
        accounts = []
        restricted = 0.0
        for acct in acct_list:
            aid = str(acct["id"])
            sums = sums_by_account.get(aid, {"credits": 0, "debits": 0})
            meta = acct.get("metadata") if isinstance(acct.get("metadata"), dict) else {}
            restr = float(meta.get("restricted_amount") or 0)
            restricted += restr
            opening = float(acct.get("opening_balance") or 0)
            snap = build_account_snapshot(
                bank_account_id=aid,
                account_name=str(acct.get("account_name") or ""),
                opening_balance=opening,
                inflows=float(sums.get("credits") or 0),
                outflows=float(sums.get("debits") or 0),
                restricted=restr,
            )
            accounts.append(snap)

        expected_collections = self._expected_collections(org_id)
        upcoming = self._upcoming_payments(org_id)
        return build_position(
            accounts=accounts,
            expected_collections=expected_collections,
            upcoming_payments=upcoming,
            restricted_cash=restricted,
        )

    def snapshot_account(self, org_id: str, *, bank_account_id: str, position_date: str | None = None) -> dict:
        pos_date = position_date or date.today().isoformat()
        acct = bank_account_repository.get(org_id, bank_account_id=bank_account_id)
        if not acct:
            raise ValueError("Bank account not found")
        prev = cash_position_repository.latest_closing(org_id, bank_account_id=bank_account_id, before_date=pos_date)
        opening = prev if prev is not None else float(acct.get("opening_balance") or 0)
        daily = bank_transaction_repository.sum_for_date(org_id, bank_account_id=bank_account_id, position_date=pos_date, reconciled_only=True)
        inflows = float(daily.get("credits") or 0)
        outflows = float(daily.get("debits") or 0)
        closing = opening + inflows - outflows
        return cash_position_repository.upsert(
            org_id,
            bank_account_id=bank_account_id,
            position_date=pos_date,
            opening_balance=opening,
            inflows=inflows,
            outflows=outflows,
            closing_balance=closing,
        )

    def snapshot_all(self, org_id: str, *, position_date: str | None = None) -> list[dict]:
        results = []
        for acct in bank_account_repository.list(org_id, active_only=True):
            results.append(self.snapshot_account(org_id, bank_account_id=str(acct["id"]), position_date=position_date))
        return results

    def refresh_and_emit(self, org_id: str) -> dict:
        self.snapshot_all(org_id)
        position = self.compute_live_position(org_id)
        emit_cash_position_updated(org_id, position=position)
        try:
            from app.modules.erp.treasury.services.treasury_realtime_service import treasury_realtime_service

            treasury_realtime_service.push_cash_position_updated(org_id, position=position)
        except Exception:
            pass
        return position

    def history(self, org_id: str, *, bank_account_id: str | None = None, limit: int = 90) -> list[dict]:
        return cash_position_repository.list_history(org_id, bank_account_id=bank_account_id, limit=limit)

    def _expected_collections(self, org_id: str) -> float:
        try:
            from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository

            total = 0.0
            for inv in ar_invoice_repository.list_outstanding(org_id):
                total += max(0.0, float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0))
            return round(total, 2)
        except Exception:
            return 0.0

    def _upcoming_payments(self, org_id: str) -> float:
        through = (date.today() + timedelta(days=30)).isoformat()
        treasury_total = payment_request_repository.sum_upcoming(org_id, through_date=through)
        ap_total = 0.0
        try:
            from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository

            for p in payment_repository.list(org_id, status="scheduled"):
                ap_total += float(p.get("amount") or 0)
        except Exception:
            pass
        return round(treasury_total + ap_total, 2)


cash_position_service = CashPositionService()
