from __future__ import annotations

from app.modules.erp.tax.validators.gstin_validator import state_from_gstin

DEFAULT_GST_RATES = {0, 0.25, 3, 5, 12, 18, 28}


def _valid_rates(org_id: str | None) -> set[float]:
    if not org_id:
        return DEFAULT_GST_RATES
    try:
        from app.modules.erp.tax.repositories.tax_rate_repository import tax_rate_repository

        rates = {float(r["gst_rate"]) for r in tax_rate_repository.list_active(org_id)}
        return rates or DEFAULT_GST_RATES
    except Exception:
        return DEFAULT_GST_RATES


def determine_place_of_supply(*, supplier_state: str, customer_state: str) -> str:
    return customer_state or supplier_state


def is_intra_state(supplier_state: str, place_of_supply: str) -> bool:
    return str(supplier_state).zfill(2) == str(place_of_supply).zfill(2)


def split_gst_amount(
    *,
    taxable_value: float,
    gst_rate: float,
    supplier_state: str,
    place_of_supply: str,
    org_id: str | None = None,
) -> dict:
    valid = _valid_rates(org_id)
    if gst_rate not in valid and gst_rate > 0:
        raise ValueError(f"Unsupported GST rate: {gst_rate}")
    total_tax = round(taxable_value * gst_rate / 100, 2)
    if total_tax <= 0:
        return {"cgst_amount": 0.0, "sgst_amount": 0.0, "igst_amount": 0.0, "cess_amount": 0.0}
    if is_intra_state(supplier_state, place_of_supply):
        half = round(total_tax / 2, 2)
        return {"cgst_amount": half, "sgst_amount": round(total_tax - half, 2), "igst_amount": 0.0, "cess_amount": 0.0}
    return {"cgst_amount": 0.0, "sgst_amount": 0.0, "igst_amount": total_tax, "cess_amount": 0.0}


def components_from_tax_code(tax_code: str, amount: float) -> dict:
    code = str(tax_code or "").upper()
    if "CGST" in code:
        return {"cgst_amount": amount, "sgst_amount": 0.0, "igst_amount": 0.0}
    if "SGST" in code:
        return {"cgst_amount": 0.0, "sgst_amount": amount, "igst_amount": 0.0}
    if "IGST" in code:
        return {"cgst_amount": 0.0, "sgst_amount": 0.0, "igst_amount": amount}
    return {"cgst_amount": 0.0, "sgst_amount": 0.0, "igst_amount": amount}


def build_gst_transaction(
    *,
    gst_type: str,
    taxable_value: float,
    gst_rate: float,
    supplier_state: str,
    party_gstin: str | None,
    place_of_supply: str | None = None,
    export_zero_rated: bool = False,
    line_components: list[dict] | None = None,
    org_id: str | None = None,
) -> dict:
    pos = place_of_supply or state_from_gstin(party_gstin) or supplier_state
    if export_zero_rated or gst_type == "export":
        return {
            "gst_type": "export",
            "taxable_value": taxable_value,
            "cgst_amount": 0.0,
            "sgst_amount": 0.0,
            "igst_amount": 0.0,
            "cess_amount": 0.0,
            "gst_rate": 0.0,
            "place_of_supply": pos,
        }
    if line_components:
        cgst = sum(float(c.get("cgst_amount") or 0) for c in line_components)
        sgst = sum(float(c.get("sgst_amount") or 0) for c in line_components)
        igst = sum(float(c.get("igst_amount") or 0) for c in line_components)
        return {
            "gst_type": gst_type,
            "taxable_value": taxable_value,
            "cgst_amount": round(cgst, 2),
            "sgst_amount": round(sgst, 2),
            "igst_amount": round(igst, 2),
            "cess_amount": 0.0,
            "gst_rate": gst_rate,
            "place_of_supply": pos,
        }
    split = split_gst_amount(
        taxable_value=taxable_value,
        gst_rate=gst_rate,
        supplier_state=supplier_state,
        place_of_supply=pos,
    )
    return {"gst_type": gst_type, "taxable_value": taxable_value, "gst_rate": gst_rate, "place_of_supply": pos, **split}
