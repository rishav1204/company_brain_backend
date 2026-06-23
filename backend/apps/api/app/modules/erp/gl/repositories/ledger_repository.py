from __future__ import annotations

from uuid import uuid4

from app.services.db import set_rls_org


class LedgerRepository:
    def create_batch(self, conn, org_id: str, *, batch_number: str, posted_by: str | None) -> dict:
        bid = str(uuid4())
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO erp.ledger_batches (id, org_id, batch_number, posting_status, posted_by, posted_at)
                VALUES (%s::uuid, %s::uuid, %s, 'posted', %s::uuid, NOW())
                RETURNING id::text, batch_number, posting_status, posted_at::text, created_at::text
                """,
                (bid, org_id, batch_number, posted_by),
            )
            return dict(cur.fetchone() or {"id": bid})

    def insert_entries(self, conn, org_id: str, *, batch_id: str, fiscal_period_id: str, posting_date: str, lines: list[dict]) -> int:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            for l in lines:
                eid = str(uuid4())
                cur.execute(
                    """
                    INSERT INTO erp.ledger_entries (
                      id, org_id, batch_id, journal_id, account_id, entry_type,
                      debit_amount, credit_amount, currency_code, exchange_rate,
                      posting_date, fiscal_period_id, reference_type, reference_id, cost_center_id
                    )
                    VALUES (
                      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s,
                      %s::numeric, %s::numeric, %s, %s::numeric,
                      %s::date, %s::uuid, %s, %s::uuid, %s::uuid
                    )
                    """,
                    (
                        eid,
                        org_id,
                        batch_id,
                        l.get("journal_id"),
                        l["account_id"],
                        l.get("entry_type") or "journal",
                        float(l.get("debit_amount") or 0),
                        float(l.get("credit_amount") or 0),
                        l.get("currency_code") or "INR",
                        float(l.get("exchange_rate") or 1),
                        posting_date,
                        fiscal_period_id,
                        l.get("reference_type"),
                        l.get("reference_id"),
                        l.get("cost_center_id"),
                    ),
                )
        return len(lines)

    def upsert_balance(
        self,
        conn,
        org_id: str,
        *,
        account_id: str,
        fiscal_period_id: str,
        debit_delta: float,
        credit_delta: float,
        closing_balance: float,
    ) -> None:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            rid = str(uuid4())
            cur.execute(
                """
                INSERT INTO erp.account_balances (
                  id, org_id, account_id, fiscal_period_id, debit_total, credit_total, closing_balance, updated_at
                )
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::numeric, %s::numeric, %s::numeric, NOW())
                ON CONFLICT (org_id, account_id, fiscal_period_id) DO UPDATE
                SET debit_total = erp.account_balances.debit_total + EXCLUDED.debit_total,
                    credit_total = erp.account_balances.credit_total + EXCLUDED.credit_total,
                    closing_balance = erp.account_balances.closing_balance + EXCLUDED.closing_balance,
                    updated_at = NOW()
                """,
                (rid, org_id, account_id, fiscal_period_id, debit_delta, credit_delta, closing_balance),
            )


ledger_repository = LedgerRepository()

