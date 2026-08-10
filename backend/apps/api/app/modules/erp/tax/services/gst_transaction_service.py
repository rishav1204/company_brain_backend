from __future__ import annotations

import re

from app.modules.erp.tax.engine.gst_engine import build_gst_transaction, components_from_tax_code
from app.modules.erp.tax.events.tax_events import emit_gst_transaction_recorded
from app.modules.erp.tax.repositories.gst_repository import gst_registration_repository, gst_transaction_repository
from app.modules.erp.tax.services.itc_service import itc_service
from app.modules.erp.tax.services.tax_rate_service import tax_rate_service
from app.modules.erp.tax.validators.gstin_validator import state_from_gstin

_GST_TYPE_ALIASES = {
    "credit_note": "credit_note",
    "creditnote": "credit_note",
    "cn": "credit_note",
    "debit_note": "debit_note",
    "debitnote": "debit_note",
    "dn": "debit_note",
    "reverse_charge": "reverse_charge",
    "rcm": "reverse_charge",
    "import": "import",
    "purchase": "purchase",
    "sales": "sales",
    "export": "export",
}


def _resolve_gst_type(meta: dict, *, default: str, is_ap: bool) -> str:
    for key in ("document_type", "invoice_kind", "gst_type", "invoice_type"):
        raw = str(meta.get(key) or "").lower().strip()
        if raw in _GST_TYPE_ALIASES:
            return _GST_TYPE_ALIASES[raw]
    if meta.get("reverse_charge") or meta.get("is_rcm"):
        return "reverse_charge"
    if meta.get("is_import"):
        return "import"
    if meta.get("is_credit_note"):
        return "credit_note"
    if meta.get("is_debit_note"):
        return "debit_note"
    return default


def _extract_hsn_sac(lines: list[dict], meta: dict, *, require_for_taxable: bool = False) -> str | None:
    if meta.get("hsn_sac"):
        return str(meta["hsn_sac"])[:16]
    for line in lines:
        if line.get("hsn_sac"):
            return str(line["hsn_sac"])[:16]
    for line in lines:
        tax_code = str(line.get("tax_code") or "").strip()
        if tax_code and require_for_taxable:
            raise ValueError("hsn_sac required on invoice line or metadata for taxable GST lines")
        desc = str(line.get("description") or "")
        match = re.search(r"\b(\d{4,8})\b", desc)
        if match:
            return match.group(1)
        if tax_code.isdigit() and len(tax_code) >= 4:
            return tax_code[:16]
    if require_for_taxable and any(float(line.get("amount") or 0) > 0 for line in lines):
        raise ValueError("hsn_sac required for GST compliance when taxable amounts present")
    return None


def _resolve_place_of_supply(*, party_gstin: str | None, customer_state: str | None, meta: dict, supplier_state: str) -> str:
    if meta.get("place_of_supply"):
        return str(meta["place_of_supply"])[:2]
    if customer_state:
        return str(customer_state)[:2]
    if party_gstin:
        return state_from_gstin(party_gstin) or supplier_state
    if meta.get("b2c") or meta.get("consumer_supply"):
        return str(meta.get("consumer_state") or supplier_state)[:2]
    return supplier_state


class GstTransactionService:
    def _return_period(self, invoice_date: str) -> str:
        return str(invoice_date)[:7]

    def _supplier_state(self, org_id: str) -> str:
        reg = gst_registration_repository.get_primary(org_id)
        if reg:
            return str(reg.get("state_code") or "27")
        return "27"

    def _load_line_components(self, org_id: str, *, table: str, invoice_id: str) -> tuple[list[dict], list[dict]]:
        line_components: list[dict] = []
        lines: list[dict] = []
        try:
            from app.services.db import get_db_conn, set_rls_org

            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT line_type, tax_code, amount, description FROM erp.{table} WHERE org_id=%s::uuid AND invoice_id=%s::uuid",
                        (org_id, invoice_id),
                    )
                    for row in cur.fetchall() or []:
                        lines.append(dict(row))
                        if str(row.get("line_type") if "line_type" in row else "") == "gst" or "gst" in str(row.get("tax_code") or "").lower():
                            comp = components_from_tax_code(str(row["tax_code"]), float(row["amount"]))
                            line_components.append(comp)
        except Exception:
            pass
        return line_components, lines

    def _build_ap_invoice_tx_fields(self, org_id: str, *, invoice_id: str) -> dict | None:
        from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
        from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository

        inv = invoice_repository.get(org_id, invoice_id=invoice_id)
        if not inv:
            return None
        vendor = vendor_repository.get(org_id, vendor_id=str(inv["vendor_id"])) or {}
        supplier_state = self._supplier_state(org_id)
        party_gstin = vendor.get("gstin")
        taxable = float(inv.get("invoice_amount") or 0)
        gst_amount = float(inv.get("gst_amount") or 0)
        invoice_date = str(inv.get("invoice_date") or "")[:10]
        meta = inv.get("metadata") if isinstance(inv.get("metadata"), dict) else {}
        vendor_meta = vendor.get("metadata") if isinstance(vendor.get("metadata"), dict) else {}

        line_components, lines = self._load_line_components(org_id, table="ap_invoice_lines", invoice_id=invoice_id)
        if not line_components:
            with_gst = [l for l in lines if l.get("tax_code")]
            for row in with_gst:
                if "gst" in str(row.get("tax_code") or "").lower() or str(row.get("line_type") or "") == "gst":
                    line_components.append(components_from_tax_code(str(row["tax_code"]), float(row["amount"])))

        gst_rate = round(gst_amount / taxable * 100, 2) if taxable > 0 and gst_amount > 0 else 0.0
        hsn_sac = _extract_hsn_sac(lines, meta, require_for_taxable=gst_amount > 0)
        gst_rate = tax_rate_service.resolve_rate(org_id, hsn_sac=hsn_sac, computed_rate=gst_rate)
        gst_type = _resolve_gst_type(meta, default="purchase", is_ap=True)
        if vendor_meta.get("is_import_vendor") or meta.get("is_import"):
            gst_type = "import"

        pos = _resolve_place_of_supply(
            party_gstin=party_gstin,
            customer_state=None,
            meta={**vendor_meta, **meta},
            supplier_state=supplier_state,
        )
        tx_data = build_gst_transaction(
            gst_type=gst_type,
            taxable_value=taxable,
            gst_rate=gst_rate,
            supplier_state=supplier_state,
            party_gstin=party_gstin,
            place_of_supply=pos,
            line_components=line_components if line_components else None,
            org_id=org_id,
        )
        return {
            "source_type": "ap_invoice",
            "source_id": invoice_id,
            "invoice_date": invoice_date,
            "party_gstin": party_gstin,
            "place_of_supply": pos,
            "hsn_sac": hsn_sac,
            "return_period": self._return_period(invoice_date),
            "metadata": {"invoice_number": inv.get("invoice_number"), **meta},
            **tx_data,
        }

    def record_from_ap_invoice(self, org_id: str, *, invoice_id: str) -> list[dict]:
        fields = self._build_ap_invoice_tx_fields(org_id, invoice_id=invoice_id)
        if not fields:
            return []
        row = gst_transaction_repository.create(org_id, **fields)
        if fields.get("gst_type") in {"purchase", "reverse_charge", "import"}:
            itc_service.create_from_purchase(
                org_id,
                gst_transaction_id=str(row["id"]),
                gst_transaction={**fields, "id": row["id"], "metadata": fields.get("metadata") or {}},
            )
        emit_gst_transaction_recorded(org_id, gst_transaction_id=str(row["id"]), source_type="ap_invoice", source_id=invoice_id)
        return [row]

    def _build_ar_invoice_tx_fields(self, org_id: str, *, invoice_id: str) -> dict | None:
        from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
        from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository
        from app.modules.erp.accounts_receivable.repositories.customer_address_repository import customer_address_repository

        inv = ar_invoice_repository.get(org_id, invoice_id=invoice_id)
        if not inv:
            return None
        customer = customer_repository.get(org_id, customer_id=str(inv["customer_id"])) or {}
        supplier_state = self._supplier_state(org_id)
        party_gstin = customer.get("gstin")
        taxable = float(inv.get("subtotal") or 0)
        gst_amount = float(inv.get("gst_amount") or 0)
        invoice_date = str(inv.get("invoice_date") or "")[:10]
        meta = inv.get("metadata") if isinstance(inv.get("metadata"), dict) else {}
        export_zero = bool(meta.get("export_zero_rated"))

        customer_state = None
        try:
            addresses = customer_address_repository.list_by_customer(org_id, customer_id=str(inv["customer_id"]))
            primary = next((a for a in addresses if a.get("is_primary")), addresses[0] if addresses else None)
            if primary:
                customer_state = primary.get("place_of_supply") or primary.get("state_code")
        except Exception:
            pass

        line_components, lines = self._load_line_components(org_id, table="ar_invoice_lines", invoice_id=invoice_id)
        if not line_components:
            for row in lines:
                if "gst" in str(row.get("tax_code") or "").lower() or str(row.get("line_type") or "") == "gst":
                    line_components.append(components_from_tax_code(str(row["tax_code"]), float(row["amount"])))

        gst_rate = round(gst_amount / taxable * 100, 2) if taxable > 0 and gst_amount > 0 else 0.0
        hsn_sac = _extract_hsn_sac(lines, meta, require_for_taxable=gst_amount > 0)
        gst_rate = tax_rate_service.resolve_rate(org_id, hsn_sac=hsn_sac, computed_rate=gst_rate)
        default_type = "export" if export_zero else "sales"
        gst_type = _resolve_gst_type(meta, default=default_type, is_ap=False)

        pos = _resolve_place_of_supply(
            party_gstin=party_gstin,
            customer_state=str(customer_state) if customer_state else None,
            meta=meta,
            supplier_state=supplier_state,
        )
        tx_data = build_gst_transaction(
            gst_type=gst_type,
            taxable_value=taxable,
            gst_rate=gst_rate,
            supplier_state=supplier_state,
            party_gstin=party_gstin,
            place_of_supply=pos,
            export_zero_rated=export_zero,
            line_components=line_components if line_components else None,
            org_id=org_id,
        )
        return {
            "source_type": "ar_invoice",
            "source_id": invoice_id,
            "invoice_date": invoice_date,
            "party_gstin": party_gstin,
            "place_of_supply": pos,
            "hsn_sac": hsn_sac,
            "return_period": self._return_period(invoice_date),
            "metadata": {"invoice_number": inv.get("invoice_number"), **meta},
            **tx_data,
        }

    def record_from_source_with_conn(self, conn, org_id: str, *, source_type: str, source_id: str) -> list[dict]:
        """
        INT-06: record GST inside caller transaction when required (posting consistency).
        Supports AP and AR invoice sources atomically.
        """
        if source_type in {"ap_invoice", "erp.ap_invoice"}:
            fields = self._build_ap_invoice_tx_fields(org_id, invoice_id=source_id)
            if not fields:
                return []
            row = gst_transaction_repository.create_conn(conn, org_id, **fields)
            return [row]
        if source_type in {"ar_invoice", "sales_invoice", "erp.ar_invoice"}:
            fields = self._build_ar_invoice_tx_fields(org_id, invoice_id=source_id)
            if not fields:
                return []
            row = gst_transaction_repository.create_conn(conn, org_id, **fields)
            return [row]
        return []

    def record_from_ar_invoice(self, org_id: str, *, invoice_id: str) -> list[dict]:
        fields = self._build_ar_invoice_tx_fields(org_id, invoice_id=invoice_id)
        if not fields:
            return []
        row = gst_transaction_repository.create(
            org_id,
            source_type=fields.pop("source_type"),
            source_id=fields.pop("source_id"),
            invoice_date=fields.pop("invoice_date"),
            party_gstin=fields.pop("party_gstin"),
            place_of_supply=fields.pop("place_of_supply"),
            hsn_sac=fields.pop("hsn_sac"),
            return_period=fields.pop("return_period"),
            metadata=fields.pop("metadata"),
            **fields,
        )
        emit_gst_transaction_recorded(org_id, gst_transaction_id=str(row["id"]), source_type="ar_invoice", source_id=invoice_id)
        return [row]

    def record_from_source(self, org_id: str, *, source_type: str, source_id: str) -> list[dict]:
        if source_type in {"ap_invoice", "erp.ap_invoice"}:
            return self.record_from_ap_invoice(org_id, invoice_id=source_id)
        if source_type in {"ar_invoice", "sales_invoice", "erp.ar_invoice"}:
            return self.record_from_ar_invoice(org_id, invoice_id=source_id)
        return []


gst_transaction_service = GstTransactionService()
