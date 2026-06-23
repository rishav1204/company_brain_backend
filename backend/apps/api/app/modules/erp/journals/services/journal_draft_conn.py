"""Connection-scoped journal draft helpers (no side effects — caller commits)."""
from __future__ import annotations

import uuid

from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository
from app.modules.erp.journals.repositories.journal_repository import journal_repository
from app.modules.erp.journals.validators.journal_validator import journal_validator


def create_draft_with_conn(
    conn,
    org_id: str,
    *,
    created_by: str | None,
    journal_type: str,
    posting_date: str,
    description: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    currency_code: str = "INR",
    exchange_rate: float = 1.0,
    company_id: str | None = None,
    lines: list[dict] | None = None,
    idempotency_key: str | None = None,
) -> dict:
    if idempotency_key:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text FROM erp.journals
                WHERE org_id = %s::uuid AND idempotency_key = %s
                LIMIT 1
                """,
                (org_id, idempotency_key),
            )
            row = cur.fetchone()
            if row:
                jid = str(row["id"])
                journal = journal_repository.get_conn(conn, org_id, journal_id=jid)
                jlines = journal_line_repository.list_by_journal_conn(conn, org_id, journal_id=jid)
                return {"journal": journal, "lines": jlines}

    journal_validator.validate_journal_type(journal_type)
    if lines:
        journal_validator.validate_lines(lines)
        journal_validator.validate_accounts_postable(org_id, lines)

    journal = journal_repository.create_conn(
        conn,
        org_id,
        journal_number="JN-" + uuid.uuid4().hex[:12].upper(),
        journal_type=journal_type,
        posting_date=posting_date,
        description=description,
        source_type=source_type,
        source_id=source_id,
        currency_code=currency_code,
        exchange_rate=exchange_rate,
        created_by=created_by,
        company_id=company_id,
        idempotency_key=idempotency_key,
    )
    jid = str(journal["id"])
    if lines:
        journal_line_repository.replace_lines_conn(conn, org_id, journal_id=jid, lines=lines)
    jlines = journal_line_repository.list_by_journal_conn(conn, org_id, journal_id=jid)
    return {"journal": journal, "lines": jlines}


def approve_with_conn(
    conn,
    org_id: str,
    *,
    journal_id: str,
    approver_id: str,
) -> dict:
    journal = journal_repository.get_conn(conn, org_id, journal_id=journal_id)
    if not journal:
        raise ValueError("Journal not found")
    status = str(journal.get("journal_status"))
    if status not in {"draft", "pending_approval"}:
        raise ValueError(f"Cannot approve journal in status '{status}'")
    lines = journal_line_repository.list_by_journal_conn(conn, org_id, journal_id=journal_id)
    from app.modules.erp.journals.services.journal_validation_service import journal_validation_service

    journal_validation_service.validate_approve(org_id, journal=journal, lines=lines)
    journal_repository.set_status_conn(
        conn,
        org_id,
        journal_id=journal_id,
        journal_status="approved",
        approved_by=approver_id,
    )
    return {"journal_id": journal_id, "journal_status": "approved"}
