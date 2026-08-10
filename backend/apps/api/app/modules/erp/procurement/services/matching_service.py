from __future__ import annotations

from app.modules.erp.accounts_payable.repositories.invoice_line_repository import invoice_line_repository
from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
from app.modules.erp.procurement.repositories.grn_repository import grn_repository
from app.modules.erp.procurement.repositories.match_repository import match_repository
from app.modules.erp.procurement.repositories.po_repository import po_repository
from app.modules.erp.procurement.services.procurement_policy_service import procurement_policy_service
from app.modules.erp.procurement.validators.matching_validator import ensure_invoice_approvable, ensure_overridable
from app.modules.erp.procurement.events.procurement_events import emit_match_completed, emit_match_exception
from app.modules.erp.procurement.workflows.exception_workflow import exception_workflow_metadata


def _pct_variance(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else 100.0
    return abs(actual - expected) / abs(expected) * 100


def _within_tolerance(variance_pct: float, tolerance_pct: float) -> bool:
    return variance_pct <= tolerance_pct


def _po_requires_grn(po: dict, po_items: list[dict]) -> bool:
    """Stock/service POs always require GRN for 3-way match (SEC-36)."""
    has_stock_or_service = any(float(item.get("quantity") or 0) > 0 for item in po_items)
    if has_stock_or_service:
        return True
    meta = po.get("metadata") if isinstance(po.get("metadata"), dict) else {}
    if meta.get("requires_grn") is False:
        return False
    if meta.get("requires_grn") is True:
        return True
    return False


def _invoice_line_for_po_item(invoice_lines: list[dict], po_item_id: str, index: int, *, allow_index_fallback: bool = False) -> dict | None:
    for line in invoice_lines:
        if str(line.get("po_item_id") or "") == po_item_id:
            return line
    # INT-25: never "index match" invoice lines to PO lines.
    # A missing `po_item_id` linkage must surface as an exception, not silently match the wrong line.
    return None


class MatchingService:
    def run_match(
        self,
        org_id: str,
        *,
        po_id: str,
        grn_id: str | None = None,
        ap_invoice_id: str | None = None,
    ) -> dict:
        po = po_repository.get(org_id, po_id=po_id)
        if not po:
            raise ValueError("PO not found")
        tolerances = procurement_policy_service.get_tolerances(org_id)
        po_items = po_repository.list_items(org_id, po_id=po_id)
        requires_grn = _po_requires_grn(po, po_items)
        if requires_grn and not grn_id:
            raise ValueError("GRN is required for 3-way match on stock/service POs")
        grn_items: list[dict] = []
        if grn_id:
            grn_items = grn_repository.list_items(org_id, grn_id=grn_id)

        invoice = invoice_repository.get(org_id, invoice_id=ap_invoice_id) if ap_invoice_id else None
        invoice_lines = invoice_line_repository.list_by_invoice(org_id, invoice_id=ap_invoice_id) if ap_invoice_id else []

        line_results: list[dict] = []
        issues = 0
        for idx, po_item in enumerate(po_items):
            po_item_id = str(po_item["id"])
            grn_line = next((g for g in grn_items if str(g.get("po_item_id")) == po_item_id), None)
            inv_line = _invoice_line_for_po_item(invoice_lines, po_item_id, idx, allow_index_fallback=False)
            po_qty = float(po_item.get("quantity") or 0)
            po_price = float(po_item.get("unit_price") or 0)
            po_amount = float(po_item.get("amount") or round(po_qty * po_price, 2))
            grn_qty = float(grn_line.get("accepted_quantity") or 0) if grn_line else (po_qty if not requires_grn else 0)
            if inv_line and inv_line.get("quantity") is not None:
                inv_qty = float(inv_line.get("quantity") or 0)
            elif inv_line and po_qty > 0 and float(inv_line.get("amount") or 0) > 0:
                inv_qty = po_qty
            else:
                inv_qty = po_qty if inv_line else 0
            if inv_line and inv_line.get("unit_price") is not None:
                inv_price = float(inv_line.get("unit_price") or 0)
            elif inv_line and inv_qty > 0:
                inv_price = float(inv_line.get("amount") or 0) / inv_qty
            else:
                inv_price = po_price
            inv_amount = float(inv_line.get("amount") or round(inv_qty * inv_price, 2)) if inv_line else po_amount

            qty_var = _pct_variance(inv_qty, grn_qty if requires_grn else po_qty)
            price_var = _pct_variance(inv_price, po_price)
            amount_var = _pct_variance(inv_amount, po_amount)
            qty_ok = _within_tolerance(qty_var, tolerances["qty_tolerance_pct"])
            price_ok = _within_tolerance(price_var, tolerances["price_tolerance_pct"])
            amount_ok = _within_tolerance(amount_var, tolerances["amount_tolerance_pct"])
            line_ok = qty_ok and price_ok and amount_ok
            if requires_grn and not grn_line:
                line_ok = False
            if not line_ok:
                issues += 1
            line_results.append({
                "po_item_id": po_item_id,
                "grn_item_id": str(grn_line.get("id")) if grn_line else None,
                "invoice_line_id": str(inv_line.get("id")) if inv_line else None,
                "po_qty": po_qty,
                "grn_qty": grn_qty,
                "invoice_qty": inv_qty,
                "po_price": po_price,
                "invoice_price": inv_price,
                "qty_variance_pct": round(qty_var, 4),
                "price_variance_pct": round(price_var, 4),
                "amount_variance_pct": round(amount_var, 4),
                "matched": line_ok,
            })

        po_total = float(po.get("total_amount") or 0)
        grn_total = sum(
            float(pi.get("unit_price") or 0) * float(g.get("accepted_quantity") or 0)
            for g in grn_items
            for pi in po_items
            if str(g.get("po_item_id")) == str(pi.get("id"))
        ) if grn_items else (po_total if not requires_grn else 0)
        inv_total = float(invoice.get("total_amount") or 0) if invoice else po_total
        header_amount_var = _pct_variance(inv_total, po_total)
        header_ok = _within_tolerance(header_amount_var, tolerances["amount_tolerance_pct"])

        if issues == 0 and header_ok and all(l.get("matched") for l in line_results):
            match_status = "matched"
        elif issues <= 1 and header_ok and requires_grn:
            match_status = "matched_within_tolerance"
        elif issues > 0:
            match_status = "exception"
        else:
            match_status = "rejected"

        score = max(0, 100 - issues * 20 - (0 if header_ok else 30))
        variance_json = {
            "lines": line_results,
            "header": {
                "po_total": po_total,
                "grn_total": round(grn_total, 2),
                "invoice_total": inv_total,
                "amount_variance_pct": round(header_amount_var, 4),
                "requires_grn": requires_grn,
            },
            "tolerances": tolerances,
        }

        existing = match_repository.get_for_invoice(org_id, ap_invoice_id=ap_invoice_id) if ap_invoice_id else None
        if existing:
            record = match_repository.update_match(
                org_id,
                match_id=str(existing["id"]),
                match_status=match_status,
                match_score=score,
                variance_json=variance_json,
                ap_invoice_id=ap_invoice_id,
            )
            match_id = str(existing["id"])
        else:
            record = match_repository.create(
                org_id,
                po_id=po_id,
                grn_id=grn_id,
                ap_invoice_id=ap_invoice_id,
                match_score=score,
                match_status=match_status,
                variance_json=variance_json,
            )
            match_id = str(record.get("id"))

        if invoice and ap_invoice_id:
            meta = invoice.get("metadata") if isinstance(invoice.get("metadata"), dict) else {}
            meta.update({"po_amount": po_total, "grn_amount": grn_total, "match_id": match_id, "match_status": match_status})
            invoice_repository.update(org_id, invoice_id=ap_invoice_id, metadata=meta)

        if match_status == "exception":
            emit_match_exception(org_id, match_id=match_id, po_id=po_id, variance=variance_json)
        else:
            emit_match_completed(org_id, match_id=match_id, match_status=match_status, po_id=po_id, ap_invoice_id=ap_invoice_id)

        return {
            "match_id": match_id,
            "match_status": match_status,
            "match_score": score,
            "variance": variance_json,
            **record,
        }

    def list_matches(self, org_id: str, *, po_id: str | None = None) -> list[dict]:
        return match_repository.list(org_id, po_id=po_id)

    def get_for_invoice(self, org_id: str, *, ap_invoice_id: str) -> dict | None:
        return match_repository.get_for_invoice(org_id, ap_invoice_id=ap_invoice_id)

    def ensure_invoice_approvable(self, org_id: str, *, ap_invoice_id: str, purchase_order_id: str | None) -> None:
        if not purchase_order_id:
            policy = procurement_policy_service.get_active(org_id)
            if policy.get("mandatory_po"):
                raise ValueError("Mandatory PO policy: invoice must be linked to a purchase order")
            return
        invoice = invoice_repository.get(org_id, invoice_id=ap_invoice_id)
        inv_meta = (invoice or {}).get("metadata") if isinstance((invoice or {}).get("metadata"), dict) else {}
        grn_id = inv_meta.get("grn_id")
        match = match_repository.get_for_invoice(org_id, ap_invoice_id=ap_invoice_id)
        if not match:
            result = self.run_match(org_id, po_id=purchase_order_id, grn_id=grn_id, ap_invoice_id=ap_invoice_id)
            match_status = result.get("match_status")
        else:
            match_status = str(match.get("match_status"))
        ensure_invoice_approvable(match_status)

    def request_override(
        self,
        org_id: str,
        *,
        match_id: str,
        actor_id: str,
        reason: str,
    ) -> dict:
        match = match_repository.get(org_id, match_id=match_id)
        if not match:
            raise ValueError("Match not found")
        ensure_overridable(str(match.get("match_status")))
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "procurement_exception",
                    "entity_id": match_id,
                    "started_by": actor_id,
                    "metadata": exception_workflow_metadata(
                        match_id=match_id,
                        po_id=str(match.get("po_id")),
                        variance=match.get("variance_json") or {},
                    ),
                },
            )
        except Exception:
            pass
        return match

    def apply_override(
        self,
        org_id: str,
        *,
        match_id: str,
        actor_id: str,
        reason: str,
        skip_workflow_check: bool = False,
    ) -> dict:
        match = match_repository.get(org_id, match_id=match_id)
        if not match:
            raise ValueError("Match not found")
        if not skip_workflow_check and not match.get("workflow_approved"):
            raise ValueError("Match exception workflow approval required")
        from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker

        try:
            enforce_maker_checker(created_by=actor_id, actor_user_id=actor_id, org_id=org_id)
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc
        return match_repository.override(
            org_id, match_id=match_id, override_by=actor_id, override_reason=reason, workflow_approved=True
        )

    def mark_exception_approved(self, org_id: str, *, match_id: str) -> dict:
        match = match_repository.get(org_id, match_id=match_id)
        if not match:
            return {}
        return match_repository.override(
            org_id,
            match_id=match_id,
            override_by=str(match.get("override_by") or "system"),
            override_reason=str(match.get("override_reason") or "workflow approved"),
            workflow_approved=True,
        )


matching_service = MatchingService()
