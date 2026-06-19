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
        grn_items: list[dict] = []
        if grn_id:
            grn_items = grn_repository.list_items(org_id, grn_id=grn_id)

        invoice = invoice_repository.get(org_id, invoice_id=ap_invoice_id) if ap_invoice_id else None
        invoice_lines = invoice_line_repository.list_by_invoice(org_id, invoice_id=ap_invoice_id) if ap_invoice_id else []

        line_results: list[dict] = []
        issues = 0
        for po_item in po_items:
            po_item_id = str(po_item["id"])
            grn_line = next((g for g in grn_items if str(g.get("po_item_id")) == po_item_id), None)
            inv_line = invoice_lines[0] if invoice_lines else None
            po_qty = float(po_item.get("quantity") or 0)
            po_price = float(po_item.get("unit_price") or 0)
            po_amount = float(po_item.get("amount") or 0)
            grn_qty = float(grn_line.get("accepted_quantity") or 0) if grn_line else 0
            inv_qty = po_qty
            inv_price = po_price
            inv_amount = float(inv_line.get("amount") or po_amount) if inv_line else po_amount

            qty_var = _pct_variance(inv_qty, grn_qty if grn_qty else po_qty)
            price_var = _pct_variance(inv_price, po_price)
            amount_var = _pct_variance(inv_amount, po_amount)
            qty_ok = _within_tolerance(qty_var, tolerances["qty_tolerance_pct"])
            price_ok = _within_tolerance(price_var, tolerances["price_tolerance_pct"])
            amount_ok = _within_tolerance(amount_var, tolerances["amount_tolerance_pct"])
            line_ok = qty_ok and price_ok and amount_ok
            if not line_ok:
                issues += 1
            line_results.append({
                "po_item_id": po_item_id,
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
        ) if grn_items else po_total
        inv_total = float(invoice.get("total_amount") or 0) if invoice else po_total
        header_amount_var = _pct_variance(inv_total, po_total)
        header_ok = _within_tolerance(header_amount_var, tolerances["amount_tolerance_pct"])

        if issues == 0 and header_ok:
            match_status = "matched"
        elif issues <= 1 and header_ok:
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
        match = match_repository.get_for_invoice(org_id, ap_invoice_id=ap_invoice_id)
        if not match:
            result = self.run_match(org_id, po_id=purchase_order_id, ap_invoice_id=ap_invoice_id)
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
