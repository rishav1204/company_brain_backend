from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ReceiptRepository:
    def create(
        self,
        org_id: str,
        *,
        document_id: str | None = None,
        claim_item_id: str | None = None,
        merchant_name: str | None = None,
        receipt_date: str | None = None,
        receipt_amount: float | None = None,
        confidence_score: float | None = None,
        receipt_hash: str | None = None,
        ocr_status: str = "pending",
        metadata: dict | None = None,
    ) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.expense_receipts (
                      id, org_id, claim_item_id, document_id, ocr_status, merchant_name,
                      receipt_date, receipt_amount, confidence_score, receipt_hash, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::date,%s::numeric,%s::numeric,%s,%s::jsonb)
                    RETURNING id::text, ocr_status, receipt_hash
                    """,
                    (
                        rid, org_id, claim_item_id, document_id, ocr_status, merchant_name,
                        receipt_date, receipt_amount, confidence_score, receipt_hash, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get(self, org_id: str, *, receipt_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, claim_item_id::text, document_id::text, ocr_status, merchant_name,
                           receipt_date::text, receipt_amount, confidence_score, receipt_hash, metadata
                    FROM erp.expense_receipts
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, receipt_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def find_by_hash(self, org_id: str, *, receipt_hash: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, claim_item_id::text, receipt_hash
                    FROM erp.expense_receipts
                    WHERE org_id = %s::uuid AND receipt_hash = %s
                    LIMIT 1
                    """,
                    (org_id, receipt_hash),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def update_ocr(
        self,
        org_id: str,
        *,
        receipt_id: str,
        ocr_status: str,
        merchant_name: str | None = None,
        receipt_date: str | None = None,
        receipt_amount: float | None = None,
        confidence_score: float | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.expense_receipts
                    SET ocr_status = %s,
                        merchant_name = COALESCE(%s, merchant_name),
                        receipt_date = COALESCE(%s::date, receipt_date),
                        receipt_amount = COALESCE(%s::numeric, receipt_amount),
                        confidence_score = COALESCE(%s::numeric, confidence_score)
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, ocr_status, merchant_name, receipt_amount
                    """,
                    (ocr_status, merchant_name, receipt_date, receipt_amount, confidence_score, org_id, receipt_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}


class PolicyRepository:
    def list_active(self, org_id: str, *, expense_type: str | None = None, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=500)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if expense_type:
                    cur.execute(
                        """
                        SELECT id::text, policy_name, expense_type, max_amount, max_per_day, per_diem_rate,
                               requires_receipt, receipt_mandatory_above, requires_manager_approval
                        FROM erp.expense_policies
                        WHERE org_id = %s::uuid AND is_active = true AND expense_type = %s
                        """,
                        (org_id, expense_type),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, policy_name, expense_type, max_amount, max_per_day, per_diem_rate,
                               requires_receipt, receipt_mandatory_above, requires_manager_approval
                        FROM erp.expense_policies
                        WHERE org_id = %s::uuid AND is_active = true
                        ORDER BY expense_type
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in cur.fetchall()]

    def list_all(self, org_id: str) -> list[dict]:
        return self.list_active(org_id)

    def record_violation(
        self,
        org_id: str,
        *,
        claim_id: str,
        policy_id: str | None,
        violation_type: str,
        severity: str,
        message: str,
    ) -> dict:
        vid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.expense_policy_violations (
                      id, org_id, claim_id, policy_id, violation_type, severity, message
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s)
                    RETURNING id::text, violation_type, severity
                    """,
                    (vid, org_id, claim_id, policy_id, violation_type, severity, message),
                )
                return dict(cur.fetchone() or {"id": vid})


class AdvanceRepository:
    def create(
        self,
        org_id: str,
        *,
        employee_id: str,
        advance_amount: float,
        issued_date: str | None = None,
        settlement_due_date: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.employee_advances (
                      id, org_id, employee_id, advance_amount, issued_date, settlement_due_date, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::numeric,COALESCE(%s::date,CURRENT_DATE),%s::date,%s::jsonb)
                    RETURNING id::text, advance_amount, status
                    """,
                    (aid, org_id, employee_id, advance_amount, issued_date, settlement_due_date, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {"id": aid})

    def list_open(self, org_id: str, *, employee_id: str | None = None, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=500)
        clauses = ["org_id = %s::uuid", "status IN ('issued','partially_adjusted')"]
        params: list = [org_id]
        if employee_id:
            clauses.append("employee_id = %s::uuid")
            params.append(employee_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, employee_id::text, advance_amount, settled_amount, status, issued_date::text
                    FROM erp.employee_advances
                    WHERE {' AND '.join(clauses)}
                    ORDER BY issued_date DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def adjust(self, org_id: str, *, advance_id: str, amount: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.employee_advances
                    SET settled_amount = settled_amount + %s::numeric,
                        status = CASE
                          WHEN settled_amount + %s::numeric >= advance_amount THEN 'adjusted'
                          ELSE 'partially_adjusted'
                        END,
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, settled_amount, status
                    """,
                    (amount, amount, org_id, advance_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}


receipt_repository = ReceiptRepository()
policy_repository = PolicyRepository()
advance_repository = AdvanceRepository()
