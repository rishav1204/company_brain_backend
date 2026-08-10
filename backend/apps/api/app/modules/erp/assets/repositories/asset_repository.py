from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class AssetRepository:
    def create(
        self,
        org_id: str,
        *,
        asset_code: str,
        asset_name: str,
        asset_category_id: str | None = None,
        purchase_date: str | None = None,
        cost: float = 0,
        salvage_value: float = 0,
        useful_life_months: int = 36,
        depreciation_method: str = "straight_line",
        company_id: str | None = None,
        location: str | None = None,
        department_id: str | None = None,
        custodian_id: str | None = None,
        cost_center_id: str | None = None,
        fixed_asset_account_id: str | None = None,
        accumulated_depreciation_account_id: str | None = None,
        depreciation_expense_account_id: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        ap_invoice_id: str | None = None,
        ap_invoice_line_id: str | None = None,
        purchase_order_id: str | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        aid = str(uuid4())
        book = float(cost)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.assets (
                      id, org_id, company_id, asset_code, asset_name, asset_category_id,
                      purchase_date, cost, salvage_value, useful_life_months, depreciation_method,
                      book_value, location, department_id, custodian_id, cost_center_id,
                      fixed_asset_account_id, accumulated_depreciation_account_id,
                      depreciation_expense_account_id, source_type, source_id,
                      ap_invoice_id, ap_invoice_line_id, purchase_order_id, created_by, metadata
                    )
                    VALUES (
                      %s::uuid,%s::uuid,%s::uuid,%s,%s,%s::uuid,%s::date,%s::numeric,%s::numeric,
                      %s,%s,%s::numeric,%s,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,
                      %s,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::jsonb
                    )
                    RETURNING id::text, asset_code, status, book_value
                    """,
                    (
                        aid, org_id, company_id, asset_code, asset_name, asset_category_id,
                        purchase_date, cost, salvage_value, useful_life_months, depreciation_method,
                        book, location, department_id, custodian_id, cost_center_id,
                        fixed_asset_account_id, accumulated_depreciation_account_id,
                        depreciation_expense_account_id, source_type, source_id,
                        ap_invoice_id, ap_invoice_line_id, purchase_order_id, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": aid})

    def get(self, org_id: str, *, asset_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, asset_code, asset_name, asset_category_id::text, purchase_date::text,
                           capitalization_date::text, cost, salvage_value, useful_life_months,
                           depreciation_method, accumulated_depreciation, impairment_amount, book_value,
                           status, workflow_approved, fixed_asset_account_id::text,
                           accumulated_depreciation_account_id::text, depreciation_expense_account_id::text,
                           capitalization_journal_id::text, location, department_id::text,
                           custodian_id::text, cost_center_id::text, source_type, source_id::text,
                           ap_invoice_id::text, ap_invoice_line_id::text, purchase_order_id::text,
                           company_id::text, metadata, created_by::text
                    FROM erp.assets WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, asset_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        status: str | None = None,
        category_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            clauses.append("status = %s")
            params.append(status)
        if category_id:
            clauses.append("asset_category_id = %s::uuid")
            params.append(category_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, asset_code, asset_name, asset_category_id::text, cost, book_value, status
                    FROM erp.assets WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def list_depreciable(self, org_id: str, limit: int = 500) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, asset_code, cost, salvage_value, useful_life_months,
                           depreciation_method, accumulated_depreciation, impairment_amount, book_value,
                           status, depreciation_expense_account_id::text,
                           accumulated_depreciation_account_id::text, company_id::text
                    FROM erp.assets
                    WHERE org_id = %s::uuid AND status IN ('active','impaired')
                      AND book_value > salvage_value
                    ORDER BY asset_code LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def set_status(
        self,
        org_id: str,
        *,
        asset_id: str,
        status: str,
        workflow_approved: bool | None = None,
        capitalization_journal_id: str | None = None,
        capitalization_date: str | None = None,
        approved_by: str | None = None,
        book_value: float | None = None,
        accumulated_depreciation: float | None = None,
        impairment_amount: float | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            return self.set_status_conn(
                conn,
                org_id,
                asset_id=asset_id,
                status=status,
                workflow_approved=workflow_approved,
                capitalization_journal_id=capitalization_journal_id,
                capitalization_date=capitalization_date,
                approved_by=approved_by,
                book_value=book_value,
                accumulated_depreciation=accumulated_depreciation,
                impairment_amount=impairment_amount,
            )

    def set_status_conn(
        self,
        conn,
        org_id: str,
        *,
        asset_id: str,
        status: str,
        workflow_approved: bool | None = None,
        capitalization_journal_id: str | None = None,
        capitalization_date: str | None = None,
        approved_by: str | None = None,
        book_value: float | None = None,
        accumulated_depreciation: float | None = None,
        impairment_amount: float | None = None,
    ) -> dict:
        sets = ["status = %s", "updated_at = NOW()"]
        params: list = [status]
        if workflow_approved is not None:
            sets.append("workflow_approved = %s")
            params.append(workflow_approved)
        if capitalization_journal_id:
            sets.append("capitalization_journal_id = %s::uuid")
            params.append(capitalization_journal_id)
        if capitalization_date:
            sets.append("capitalization_date = %s::date")
            params.append(capitalization_date)
        if approved_by:
            sets.append("approved_by = %s::uuid")
            params.append(approved_by)
        if book_value is not None:
            sets.append("book_value = %s::numeric")
            params.append(book_value)
        if accumulated_depreciation is not None:
            sets.append("accumulated_depreciation = %s::numeric")
            params.append(accumulated_depreciation)
        if impairment_amount is not None:
            sets.append("impairment_amount = %s::numeric")
            params.append(impairment_amount)
        params.extend([org_id, asset_id])
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE erp.assets SET {', '.join(sets)}
                WHERE org_id = %s::uuid AND id = %s::uuid
                RETURNING id::text, status, book_value
                """,
                tuple(params),
            )
            row = cur.fetchone()
            return dict(row) if row else {}

    def update_operational(
        self,
        org_id: str,
        *,
        asset_id: str,
        department_id: str | None = None,
        location: str | None = None,
        custodian_id: str | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.assets
                    SET department_id = COALESCE(%s::uuid, department_id),
                        location = COALESCE(%s, location),
                        custodian_id = COALESCE(%s::uuid, custodian_id),
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, department_id::text, location, custodian_id::text
                    """,
                    (department_id, location, custodian_id, org_id, asset_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}


class TransferRepository:
    def create(
        self,
        org_id: str,
        *,
        asset_id: str,
        from_department_id: str | None,
        to_department_id: str | None,
        from_location: str | None,
        to_location: str | None,
        from_custodian_id: str | None,
        to_custodian_id: str | None,
        transfer_date: str,
        reason: str | None,
        created_by: str | None,
    ) -> dict:
        tid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.asset_transfers (
                      id, org_id, asset_id, from_department_id, to_department_id,
                      from_location, to_location, from_custodian_id, to_custodian_id,
                      transfer_date, reason, created_by
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::uuid,%s::uuid,%s::date,%s,%s::uuid)
                    RETURNING id::text
                    """,
                    (
                        tid, org_id, asset_id, from_department_id, to_department_id,
                        from_location, to_location, from_custodian_id, to_custodian_id,
                        transfer_date, reason, created_by,
                    ),
                )
                return dict(cur.fetchone() or {"id": tid})


class ImpairmentRepository:
    def create(
        self,
        org_id: str,
        *,
        asset_id: str,
        impairment_date: str,
        impairment_amount: float,
        book_value_before: float,
        book_value_after: float,
        journal_id: str | None,
        reason: str | None,
        created_by: str | None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            return self.create_conn(
                conn,
                org_id,
                asset_id=asset_id,
                impairment_date=impairment_date,
                impairment_amount=impairment_amount,
                book_value_before=book_value_before,
                book_value_after=book_value_after,
                journal_id=journal_id,
                reason=reason,
                created_by=created_by,
            )

    def create_conn(
        self,
        conn,
        org_id: str,
        *,
        asset_id: str,
        impairment_date: str,
        impairment_amount: float,
        book_value_before: float,
        book_value_after: float,
        journal_id: str | None,
        reason: str | None,
        created_by: str | None,
    ) -> dict:
        iid = str(uuid4())
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO erp.asset_impairments (
                  id, org_id, asset_id, impairment_date, impairment_amount,
                  book_value_before, book_value_after, journal_id, reason, created_by
                )
                VALUES (%s::uuid,%s::uuid,%s::uuid,%s::date,%s::numeric,%s::numeric,%s::numeric,%s::uuid,%s,%s::uuid)
                RETURNING id::text
                """,
                (
                    iid, org_id, asset_id, impairment_date, impairment_amount,
                    book_value_before, book_value_after, journal_id, reason, created_by,
                ),
            )
            return dict(cur.fetchone() or {"id": iid})


class DisposalRepository:
    def create(
        self,
        org_id: str,
        *,
        asset_id: str,
        disposal_date: str,
        sale_amount: float,
        book_value: float,
        gain_loss: float,
        journal_id: str | None,
        reason: str | None,
        created_by: str | None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            return self.create_conn(
                conn,
                org_id,
                asset_id=asset_id,
                disposal_date=disposal_date,
                sale_amount=sale_amount,
                book_value=book_value,
                gain_loss=gain_loss,
                journal_id=journal_id,
                reason=reason,
                created_by=created_by,
            )

    def create_conn(
        self,
        conn,
        org_id: str,
        *,
        asset_id: str,
        disposal_date: str,
        sale_amount: float,
        book_value: float,
        gain_loss: float,
        journal_id: str | None,
        reason: str | None,
        created_by: str | None,
    ) -> dict:
        did = str(uuid4())
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO erp.asset_disposals (
                  id, org_id, asset_id, disposal_date, sale_amount, book_value,
                  gain_loss, journal_id, reason, created_by
                )
                VALUES (%s::uuid,%s::uuid,%s::uuid,%s::date,%s::numeric,%s::numeric,%s::numeric,%s::uuid,%s,%s::uuid)
                RETURNING id::text, gain_loss
                """,
                (
                    did, org_id, asset_id, disposal_date, sale_amount, book_value,
                    gain_loss, journal_id, reason, created_by,
                ),
            )
            return dict(cur.fetchone() or {"id": did})


asset_repository = AssetRepository()
transfer_repository = TransferRepository()
impairment_repository = ImpairmentRepository()
disposal_repository = DisposalRepository()
