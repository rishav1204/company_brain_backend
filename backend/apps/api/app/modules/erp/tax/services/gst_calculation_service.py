from __future__ import annotations

from app.modules.erp.tax.engine.gst_engine import build_gst_transaction, split_gst_amount


class GstCalculationService:
    def calculate(
        self,
        org_id: str,
        *,
        taxable_value: float,
        gst_rate: float,
        supplier_state: str,
        place_of_supply: str | None = None,
        party_gstin: str | None = None,
        gst_type: str = "sales",
        export_zero_rated: bool = False,
    ) -> dict:
        if export_zero_rated or gst_type == "export":
            return build_gst_transaction(
                gst_type="export",
                taxable_value=taxable_value,
                gst_rate=0,
                supplier_state=supplier_state,
                party_gstin=party_gstin,
                place_of_supply=place_of_supply,
                export_zero_rated=True,
                org_id=org_id,
            )
        pos = place_of_supply or supplier_state
        split = split_gst_amount(
            taxable_value=taxable_value,
            gst_rate=gst_rate,
            supplier_state=supplier_state,
            place_of_supply=pos,
            org_id=org_id,
        )
        total_tax = round(
            float(split["cgst_amount"]) + float(split["sgst_amount"]) + float(split["igst_amount"]),
            2,
        )
        return {
            "taxable_value": taxable_value,
            "gst_rate": gst_rate,
            "supplier_state": supplier_state,
            "place_of_supply": pos,
            "cgst_amount": split["cgst_amount"],
            "sgst_amount": split["sgst_amount"],
            "igst_amount": split["igst_amount"],
            "total_tax": total_tax,
            "gross_amount": round(taxable_value + total_tax, 2),
            "supply_type": "intrastate" if split["igst_amount"] == 0 else "interstate",
        }


gst_calculation_service = GstCalculationService()
