from __future__ import annotations

from app.modules.erp.procurement.repositories.grn_repository import grn_repository
from app.modules.erp.procurement.repositories.po_repository import po_repository
from app.modules.erp.procurement.services.matching_service import _po_requires_grn


def validate_po_invoice_prerequisites(
    org_id: str,
    *,
    purchase_order_id: str,
    goods_receipt_id: str | None,
) -> None:
    po = po_repository.get(org_id, po_id=purchase_order_id)
    if not po:
        raise ValueError("Purchase order not found")
    po_items = po_repository.list_items(org_id, po_id=purchase_order_id)
    if _po_requires_grn(po, po_items) and not goods_receipt_id:
        raise ValueError("Goods receipt (GRN) is required before creating AP invoice for stock/service POs")
    if goods_receipt_id:
        grn = grn_repository.get(org_id, grn_id=goods_receipt_id)
        if not grn:
            raise ValueError("GRN not found")
        if str(grn.get("po_id")) != purchase_order_id:
            raise ValueError("GRN does not belong to the linked purchase order")
        if str(grn.get("status")) != "confirmed":
            raise ValueError("GRN must be confirmed before invoicing")


def build_invoice_lines_from_po(
    org_id: str,
    *,
    purchase_order_id: str,
    expense_account_id: str | None = None,
    goods_receipt_id: str | None = None,
) -> list[dict]:
    po_items = po_repository.list_items(org_id, po_id=purchase_order_id)
    grn_qty_by_po_item: dict[str, float] = {}
    if goods_receipt_id:
        for gi in grn_repository.list_items(org_id, grn_id=goods_receipt_id):
            pid = str(gi.get("po_item_id") or "")
            grn_qty_by_po_item[pid] = grn_qty_by_po_item.get(pid, 0.0) + float(
                gi.get("accepted_quantity") or gi.get("received_quantity") or 0
            )
    lines: list[dict] = []
    for item in po_items:
        po_item_id = str(item["id"])
        qty = float(item.get("quantity") or 0)
        unit_price = float(item.get("unit_price") or 0)
        if goods_receipt_id and po_item_id in grn_qty_by_po_item:
            qty = grn_qty_by_po_item[po_item_id]
        amount = round(qty * unit_price, 2)
        if amount <= 0 and qty <= 0:
            continue
        lines.append({
            "po_item_id": po_item_id,
            "account_id": expense_account_id or item.get("account_id"),
            "line_type": "expense",
            "description": str(item.get("description") or item.get("item_name") or "PO line"),
            "quantity": qty,
            "unit_price": unit_price,
            "amount": amount,
            "tax_code": item.get("tax_code"),
        })
    if not lines:
        raise ValueError("No billable PO lines found for invoice")
    return lines
