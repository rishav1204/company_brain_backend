from __future__ import annotations

from app.modules.erp.inventory.engine.cogs_engine import build_receipt_journal_lines
from app.modules.erp.inventory.engine.account_resolver import resolve_grni_clearing_account
from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.services.db import get_db_conn, set_rls_org
from app.modules.erp.procurement.repositories.grn_repository import grn_repository
from app.modules.erp.procurement.repositories.po_repository import po_repository


class GrnAccrualService:
    """Post GRNI accrual journals on GRN confirm for service/non-inventory PO lines."""

    def accrue_service_lines(self, org_id: str, *, grn_id: str, actor_id: str | None) -> list[dict]:
        grn = grn_repository.get(org_id, grn_id=grn_id)
        if not grn:
            raise ValueError("GRN not found")
        po_id = str(grn.get("po_id"))
        po_items = {str(i["id"]): i for i in po_repository.list_items(org_id, po_id=po_id)}
        grni_id = resolve_grni_clearing_account(org_id)
        if not grni_id:
            raise ValueError("GRNI clearing account required for GRN accrual")
        posted: list[dict] = []
        mdate = str(grn.get("received_date") or "")[:10]
        for line in grn_repository.list_items(org_id, grn_id=grn_id):
            if line.get("inventory_item_id"):
                continue
            po_item = po_items.get(str(line.get("po_item_id"))) or {}
            qty = float(line.get("accepted_quantity") or line.get("received_quantity") or 0)
            unit_price = float(po_item.get("unit_price") or 0)
            amount = round(qty * unit_price, 2)
            if amount <= 0:
                continue
            expense_id = po_item.get("account_id") or po_item.get("expense_account_id")
            if not expense_id:
                from app.modules.erp.accounts_payable.engine.account_resolver import resolve_expense_account

                expense_id = resolve_expense_account(org_id)
            if not expense_id:
                raise ValueError("Expense account required for service GRN accrual")
            journal_lines = [
                {"account_id": expense_id, "debit_amount": amount, "credit_amount": 0, "line_description": "GRNI accrual"},
                {"account_id": grni_id, "debit_amount": 0, "credit_amount": amount, "line_description": "GRNI liability"},
            ]
            grn_item_id = str(line.get("id"))
            jid = None
            journal = None
            post_result = None
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                journal = create_draft_with_conn(
                    conn,
                    org_id,
                    created_by=actor_id,
                    journal_type="accrual",
                    posting_date=mdate,
                    description=f"GRNI accrual GRN {grn_id} line {grn_item_id}",
                    source_type="goods_receipt",
                    source_id=grn_id,
                    lines=journal_lines,
                    idempotency_key=f"grni-accrual:{grn_item_id}",
                )
                jid = str(journal["journal"]["id"])
                approve_with_conn(conn, org_id, journal_id=jid, approver_id=actor_id or "system", skip_maker_checker=True)
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=jid, posted_by=actor_id or "system", defer_side_effects=True
                )
                conn.commit()
            if journal:
                posting_orchestrator._emit_post_side_effects(
                    org_id,
                    journal_id=jid,
                    journal=journal["journal"],
                    batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                    posted_by=actor_id or "system",
                )
            posted.append({"grn_item_id": grn_item_id, "journal_id": jid, "amount": amount})
        return posted


grn_accrual_service = GrnAccrualService()
