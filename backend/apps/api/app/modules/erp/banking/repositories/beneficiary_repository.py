from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class BeneficiaryRepository:
    def create(self, org_id: str, **fields) -> dict:
        bid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.bank_beneficiaries (
                      id, org_id, beneficiary_name, account_number_encrypted, ifsc_code,
                      bank_name, vendor_id, customer_id, verified, metadata
                    ) VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s,%s::uuid,%s::uuid,%s,%s::jsonb)
                    RETURNING id::text, beneficiary_name, ifsc_code, verified, vendor_id::text, customer_id::text
                    """,
                    (
                        bid, org_id, fields["beneficiary_name"], fields["account_number_encrypted"],
                        fields["ifsc_code"], fields.get("bank_name"), fields.get("vendor_id"),
                        fields.get("customer_id"), fields.get("verified", False), Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": bid})

    def get(self, org_id: str, beneficiary_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, beneficiary_name, account_number_encrypted, ifsc_code, bank_name,
                           vendor_id::text, customer_id::text, verified, metadata
                    FROM erp.bank_beneficiaries WHERE org_id=%s::uuid AND id=%s::uuid
                    """,
                    (org_id, beneficiary_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, vendor_id: str | None = None, verified_only: bool = False, limit: int = 200) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if vendor_id:
            where.append("vendor_id = %s::uuid")
            params.append(vendor_id)
        if verified_only:
            where.append("verified = true")
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, beneficiary_name, ifsc_code, bank_name, vendor_id::text,
                           customer_id::text, verified, created_at::text
                    FROM erp.bank_beneficiaries WHERE {' AND '.join(where)}
                    ORDER BY beneficiary_name LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def set_verified(self, org_id: str, beneficiary_id: str, *, verified: bool = True) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.bank_beneficiaries SET verified=%s, updated_at=NOW()
                    WHERE org_id=%s::uuid AND id=%s::uuid
                    RETURNING id::text, verified
                    """,
                    (verified, org_id, beneficiary_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Beneficiary not found")
                return dict(row)


class StatementImportRepository:
    def create(self, org_id: str, **fields) -> dict:
        sid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.bank_statement_imports (
                      id, org_id, bank_account_id, file_format, file_hash, row_count,
                      imported_count, skipped_count, imported_by, metadata
                    ) VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s::uuid,%s::jsonb)
                    RETURNING id::text, file_format, imported_count, skipped_count
                    """,
                    (
                        sid, org_id, fields["bank_account_id"], fields["file_format"],
                        fields.get("file_hash"), fields.get("row_count", 0),
                        fields.get("imported_count", 0), fields.get("skipped_count", 0),
                        fields.get("imported_by"), Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": sid})


beneficiary_repository = BeneficiaryRepository()
statement_import_repository = StatementImportRepository()
