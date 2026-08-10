from __future__ import annotations

from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.coa.repositories.mapping_repository import mapping_repository

TAX_CODE_TO_GST_TYPE = {
    "CGST_INPUT": "cgst_input",
    "SGST_INPUT": "sgst_input",
    "IGST_INPUT": "igst_input",
    "CGST_OUTPUT": "cgst_output",
    "SGST_OUTPUT": "sgst_output",
    "IGST_OUTPUT": "igst_output",
    "REVERSE_CHARGE": "reverse_charge",
}


class GstValidator:
    def validate_lines(self, org_id: str, lines: list[dict], *, company_id: str | None = None) -> None:
        taxable_lines = []
        for line in lines:
            tax_code = str(line.get("tax_code") or "").strip().upper()
            if not tax_code:
                continue
            gst_type = TAX_CODE_TO_GST_TYPE.get(tax_code)
            if not gst_type:
                raise ValueError(f"Unknown tax_code: {tax_code}")
            taxable_lines.append((line, tax_code, gst_type))
        if not taxable_lines:
            return

        gst_mappings = mapping_repository.list_gst_mappings(org_id, company_id=company_id)
        by_gst_type = {str(m.get("gst_type")): str(m.get("account_id")) for m in gst_mappings}

        for line, tax_code, gst_type in taxable_lines:

            account_id = str(line.get("account_id") or "")
            acc = account_repository.get(org_id, account_id=account_id) or {}
            account_type = str(acc.get("account_type") or "")
            if account_type not in {"gst_input", "gst_output"}:
                raise ValueError(f"Account {account_id} must be gst_input/gst_output for tax_code {tax_code}")

            mapped_account = by_gst_type.get(gst_type)
            if not mapped_account:
                raise ValueError(
                    f"Missing COA GST mapping for {tax_code} ({gst_type}); configure via /erp/coa/mappings"
                )
            if mapped_account != account_id:
                raise ValueError(
                    f"GST account mismatch for {tax_code}: expected mapped account {mapped_account}, got {account_id}"
                )


gst_validator = GstValidator()
