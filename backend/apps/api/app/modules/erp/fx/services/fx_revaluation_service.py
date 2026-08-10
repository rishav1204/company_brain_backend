from __future__ import annotations

from app.core.config import settings
from app.modules.erp.accounts_payable.engine.account_resolver import resolve_account_by_code, resolve_account_by_type
from app.modules.erp.fx.repositories.exchange_rate_repository import exchange_rate_repository
from app.modules.erp.fx.repositories.fx_revaluation_repository import fx_revaluation_repository
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.modules.erp.security.company_resolution_service import company_resolution_service
from app.services.db import get_db_conn, set_rls_org


def _resolve_fx_gain_account(org_id: str) -> str | None:
    return resolve_account_by_type(org_id, "fx_gain") or resolve_account_by_code(org_id, "4900")


def _resolve_fx_loss_account(org_id: str) -> str | None:
    return resolve_account_by_type(org_id, "fx_loss") or resolve_account_by_code(org_id, "5900")


class FxRevaluationService:
    def _foreign_currency_balances(
        self,
        org_id: str,
        *,
        company_id: str | None,
        as_of_date: str,
    ) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                params: list = [org_id, as_of_date]
                company_clause = ""
                if company_id:
                    company_clause = """
                      AND le.account_id IN (
                        SELECT id FROM erp.chart_of_accounts
                        WHERE org_id = %s::uuid AND (company_id IS NULL OR company_id = %s::uuid)
                      )
                    """
                    params.extend([org_id, company_id])
                cur.execute(
                    f"""
                    SELECT le.account_id::text AS account_id,
                           le.currency_code,
                           COALESCE(a.account_type, 'asset') AS account_type,
                           SUM(le.debit_amount - le.credit_amount)::float8 AS inr_book_balance,
                           SUM(
                             CASE WHEN COALESCE(le.exchange_rate, 1) > 0
                                  THEN (le.debit_amount - le.credit_amount) / le.exchange_rate
                                  ELSE 0 END
                           )::float8 AS fc_balance
                    FROM erp.ledger_entries le
                    LEFT JOIN erp.chart_of_accounts a ON a.id = le.account_id
                    WHERE le.org_id = %s::uuid
                      AND le.currency_code <> 'INR'
                      AND le.posting_date <= %s::date
                      {company_clause}
                    GROUP BY le.account_id, le.currency_code, a.account_type
                    HAVING ABS(SUM(le.debit_amount - le.credit_amount)) > 0.01
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def run_revaluation(
        self,
        org_id: str,
        *,
        revaluation_date: str,
        company_id: str | None = None,
        fiscal_period_id: str | None = None,
        actor_id: str | None = None,
    ) -> dict:
        if settings.erp_require_company_id:
            company_id = company_resolution_service.resolve_for_write(
                org_id, company_id=company_id, operation="fx.revaluation.run"
            )

        fx_gain_id = _resolve_fx_gain_account(org_id)
        fx_loss_id = _resolve_fx_loss_account(org_id)
        if not fx_gain_id or not fx_loss_id:
            raise ValueError("FX gain/loss accounts required — configure account_type fx_gain/fx_loss or codes 4900/5900")

        balances = self._foreign_currency_balances(org_id, company_id=company_id, as_of_date=revaluation_date)
        if not balances:
            run = fx_revaluation_repository.create(
                org_id,
                company_id=company_id,
                fiscal_period_id=fiscal_period_id,
                revaluation_date=revaluation_date,
                total_unrealized_gain=0,
                total_unrealized_loss=0,
                details={"accounts": [], "note": "No foreign currency balances"},
            )
            return {**run, "journal_id": None}

        journal_lines: list[dict] = []
        details_accounts: list[dict] = []
        total_gain = 0.0
        total_loss = 0.0

        for bal in balances:
            currency = str(bal["currency_code"])
            rate_row = exchange_rate_repository.get_rate_for_date(
                org_id,
                from_currency=currency,
                to_currency="INR",
                rate_date=revaluation_date,
                company_id=company_id,
            )
            if not rate_row:
                details_accounts.append({**bal, "skipped": True, "reason": f"No rate for {currency}"})
                continue

            new_rate = float(rate_row["rate"])
            fc_balance = float(bal["fc_balance"] or 0)
            inr_book = float(bal["inr_book_balance"] or 0)
            new_inr = round(fc_balance * new_rate, 2)
            adjustment = round(new_inr - inr_book, 2)

            account_type = str(bal.get("account_type") or "asset").lower()
            if account_type in {"liability", "payable", "tds_payable", "tcs_payable"}:
                adjustment = -adjustment

            if abs(adjustment) < 0.01:
                continue

            account_id = str(bal["account_id"])
            if adjustment > 0:
                total_gain = round(total_gain + adjustment, 2)
                journal_lines.append(
                    {"account_id": account_id, "debit_amount": adjustment, "credit_amount": 0, "line_description": f"FX reval {currency}"}
                )
                journal_lines.append(
                    {"account_id": fx_gain_id, "debit_amount": 0, "credit_amount": adjustment, "line_description": f"Unrealized FX gain {currency}"}
                )
            else:
                amt = abs(adjustment)
                total_loss = round(total_loss + amt, 2)
                journal_lines.append(
                    {"account_id": fx_loss_id, "debit_amount": amt, "credit_amount": 0, "line_description": f"Unrealized FX loss {currency}"}
                )
                journal_lines.append(
                    {"account_id": account_id, "debit_amount": 0, "credit_amount": amt, "line_description": f"FX reval {currency}"}
                )

            details_accounts.append(
                {
                    "account_id": account_id,
                    "currency_code": currency,
                    "fc_balance": fc_balance,
                    "inr_book_balance": inr_book,
                    "new_inr_balance": new_inr,
                    "adjustment": adjustment,
                    "rate": new_rate,
                }
            )

        journal_id: str | None = None
        if journal_lines:
            journal = journal_service.create_draft(
                org_id,
                created_by=actor_id,
                journal_type="fx_revaluation",
                posting_date=revaluation_date,
                description=f"FX revaluation as of {revaluation_date}",
                source_type="fx_revaluation",
                company_id=company_id,
                lines=journal_lines,
                idempotency_key=f"fx-reval:{revaluation_date}:{company_id or 'default'}",
            )
            journal_id = str(journal["journal"]["id"])
            journal_approval_service.approve(
                org_id, journal_id=journal_id, approver_id=actor_id or "system", skip_maker_checker=True
            )
            posting_orchestrator.post_journal(org_id, journal_id=journal_id, posted_by=actor_id or "system")

        run = fx_revaluation_repository.create(
            org_id,
            company_id=company_id,
            fiscal_period_id=fiscal_period_id,
            revaluation_date=revaluation_date,
            total_unrealized_gain=total_gain,
            total_unrealized_loss=total_loss,
            journal_id=journal_id,
            details={"accounts": details_accounts},
        )
        return {**run, "journal_id": journal_id}

    def get_run(self, org_id: str, *, run_id: str) -> dict:
        row = fx_revaluation_repository.get(org_id, run_id=run_id)
        if not row:
            raise ValueError("FX revaluation run not found")
        return row

    def list_runs(self, org_id: str, *, limit: int = 50) -> list[dict]:
        return fx_revaluation_repository.list(org_id, limit=limit)


fx_revaluation_service = FxRevaluationService()
