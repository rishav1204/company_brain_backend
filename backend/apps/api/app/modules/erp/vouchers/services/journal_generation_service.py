from __future__ import annotations

from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.vouchers.events.voucher_events import emit_voucher_journal_generated
from app.modules.erp.vouchers.generators import journal_type_for_voucher, lines_for_voucher
from app.modules.erp.vouchers.repositories.voucher_line_repository import voucher_line_repository
from app.modules.erp.vouchers.repositories.voucher_repository import voucher_repository
from app.services.db import get_db_conn, set_rls_org


class JournalGenerationService:
    def generate(
        self,
        org_id: str,
        *,
        voucher_id: str,
        approver_id: str | None,
        skip_maker_checker: bool = True,
        generator_payload: dict | None = None,
    ) -> dict:
        voucher = voucher_repository.get(org_id, voucher_id=voucher_id)
        if not voucher:
            raise ValueError("Voucher not found")
        if voucher.get("journal_id"):
            return {"voucher_id": voucher_id, "journal_id": voucher["journal_id"], "status": "journal_generated"}

        vtype = str(voucher["voucher_type"])
        stored_lines = voucher_line_repository.list_by_voucher(org_id, voucher_id=voucher_id)
        payload = dict(generator_payload or {})
        if stored_lines and vtype != "journal":
            lines = [
                {
                    "account_id": line["account_id"],
                    "debit_amount": line.get("debit_amount") or 0,
                    "credit_amount": line.get("credit_amount") or 0,
                    "line_description": line.get("narration"),
                    "cost_center_id": line.get("cost_center_id"),
                    "tax_code": line.get("tax_code"),
                }
                for line in stored_lines
            ]
        elif vtype == "journal":
            payload.setdefault("lines", stored_lines)
            lines = lines_for_voucher(org_id, voucher_type=vtype, payload=payload)
        else:
            lines = lines_for_voucher(org_id, voucher_type=vtype, payload=payload)

        jid = None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            journal = create_draft_with_conn(
                conn,
                org_id,
                created_by=approver_id,
                journal_type=journal_type_for_voucher(vtype),
                posting_date=str(voucher["voucher_date"]),
                description=voucher.get("narration") or f"Voucher {voucher.get('voucher_number')}",
                source_type="voucher",
                source_id=voucher_id,
                company_id=voucher.get("company_id"),
                lines=lines,
                idempotency_key=f"voucher:{voucher_id}",
            )
            jid = str(journal["journal"]["id"])
            approve_with_conn(
                conn,
                org_id,
                journal_id=jid,
                approver_id=approver_id or "voucher-engine",
                skip_maker_checker=skip_maker_checker,
            )
            voucher_repository.link_journal_conn(conn, org_id, voucher_id=voucher_id, journal_id=jid)

        emit_voucher_journal_generated(org_id, voucher_id, journal_id=jid)
        return {"voucher_id": voucher_id, "journal_id": jid, "status": "journal_generated"}

    def generate_with_conn(
        self,
        conn,
        org_id: str,
        *,
        voucher_id: str,
        approver_id: str | None,
        skip_maker_checker: bool = True,
        generator_payload: dict | None = None,
    ) -> dict:
        voucher = voucher_repository.get(org_id, voucher_id=voucher_id)
        if not voucher:
            raise ValueError("Voucher not found")
        if voucher.get("journal_id"):
            return {"voucher_id": voucher_id, "journal_id": voucher["journal_id"], "status": "journal_generated"}

        vtype = str(voucher["voucher_type"])
        stored_lines = voucher_line_repository.list_by_voucher(org_id, voucher_id=voucher_id)
        payload = dict(generator_payload or {})
        if stored_lines and vtype != "journal":
            lines = [
                {
                    "account_id": line["account_id"],
                    "debit_amount": line.get("debit_amount") or 0,
                    "credit_amount": line.get("credit_amount") or 0,
                    "line_description": line.get("narration"),
                    "cost_center_id": line.get("cost_center_id"),
                    "tax_code": line.get("tax_code"),
                }
                for line in stored_lines
            ]
        elif vtype == "journal":
            payload.setdefault("lines", stored_lines)
            lines = lines_for_voucher(org_id, voucher_type=vtype, payload=payload)
        else:
            lines = lines_for_voucher(org_id, voucher_type=vtype, payload=payload)

        journal = create_draft_with_conn(
            conn,
            org_id,
            created_by=approver_id,
            journal_type=journal_type_for_voucher(vtype),
            posting_date=str(voucher["voucher_date"]),
            description=voucher.get("narration") or f"Voucher {voucher.get('voucher_number')}",
            source_type="voucher",
            source_id=voucher_id,
            company_id=voucher.get("company_id"),
            lines=lines,
            idempotency_key=f"voucher:{voucher_id}",
        )
        jid = str(journal["journal"]["id"])
        approve_with_conn(
            conn,
            org_id,
            journal_id=jid,
            approver_id=approver_id or "voucher-engine",
            skip_maker_checker=skip_maker_checker,
        )
        voucher_repository.link_journal_conn(conn, org_id, voucher_id=voucher_id, journal_id=jid)
        return {"voucher_id": voucher_id, "journal_id": jid, "status": "journal_generated", "journal": journal}


journal_generation_service = JournalGenerationService()
