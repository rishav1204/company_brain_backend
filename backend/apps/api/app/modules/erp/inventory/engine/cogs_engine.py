from __future__ import annotations

from app.modules.erp.inventory.engine.account_resolver import (
    resolve_cogs_account,
    resolve_grni_clearing_account,
    resolve_inventory_account,
    resolve_inventory_loss_account,
)


def build_receipt_journal_lines(
    org_id: str,
    *,
    total_cost: float,
    inventory_account_id: str | None = None,
    grni_account_id: str | None = None,
) -> list[dict]:
    inv_id = inventory_account_id or resolve_inventory_account(org_id)
    grni_id = grni_account_id or resolve_grni_clearing_account(org_id)
    if not inv_id or not grni_id:
        raise ValueError("Inventory and GRNI clearing accounts required")
    return [
        {"account_id": inv_id, "debit_amount": total_cost, "credit_amount": 0, "line_description": "Inventory receipt"},
        {"account_id": grni_id, "debit_amount": 0, "credit_amount": total_cost, "line_description": "GRNI clearing"},
    ]


def build_cogs_journal_lines(
    org_id: str,
    *,
    total_cost: float,
    cogs_account_id: str | None = None,
    inventory_account_id: str | None = None,
) -> list[dict]:
    cogs_id = cogs_account_id or resolve_cogs_account(org_id)
    inv_id = inventory_account_id or resolve_inventory_account(org_id)
    if not cogs_id or not inv_id:
        raise ValueError("COGS and inventory accounts required")
    return [
        {"account_id": cogs_id, "debit_amount": total_cost, "credit_amount": 0, "line_description": "Cost of goods sold"},
        {"account_id": inv_id, "debit_amount": 0, "credit_amount": total_cost, "line_description": "Inventory issue"},
    ]


def build_grni_clearing_lines(
    org_id: str,
    *,
    invoice_amount: float,
    payable_account_id: str,
    grni_account_id: str | None = None,
    gst_lines: list[dict] | None = None,
) -> list[dict]:
    grni_id = grni_account_id or resolve_grni_clearing_account(org_id)
    if not grni_id:
        raise ValueError("GRNI clearing account required")
    lines = [{"account_id": grni_id, "debit_amount": invoice_amount, "credit_amount": 0, "line_description": "Clear GRNI"}]
    for gl in gst_lines or []:
        amt = float(gl.get("amount") or 0)
        if amt > 0 and gl.get("account_id"):
            lines.append({
                "account_id": gl["account_id"],
                "debit_amount": amt,
                "credit_amount": 0,
                "line_description": gl.get("description") or "GST",
            })
    total_credit = invoice_amount + sum(float(gl.get("amount") or 0) for gl in (gst_lines or []))
    lines.append({
        "account_id": payable_account_id,
        "debit_amount": 0,
        "credit_amount": total_credit,
        "line_description": "Vendor payable",
    })
    return lines


def build_adjustment_journal_lines(
    org_id: str,
    *,
    value_variance: float,
    inventory_account_id: str | None = None,
    loss_account_id: str | None = None,
) -> list[dict]:
    inv_id = inventory_account_id or resolve_inventory_account(org_id)
    loss_id = loss_account_id or resolve_inventory_loss_account(org_id)
    if not inv_id or not loss_id:
        raise ValueError("Inventory and loss accounts required")
    amt = abs(value_variance)
    if value_variance < 0:
        return [
            {"account_id": loss_id, "debit_amount": amt, "credit_amount": 0, "line_description": "Inventory loss"},
            {"account_id": inv_id, "debit_amount": 0, "credit_amount": amt, "line_description": "Inventory reduction"},
        ]
    return [
        {"account_id": inv_id, "debit_amount": amt, "credit_amount": 0, "line_description": "Inventory increase"},
        {"account_id": loss_id, "debit_amount": 0, "credit_amount": amt, "line_description": "Inventory gain"},
    ]
