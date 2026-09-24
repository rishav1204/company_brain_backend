from __future__ import annotations

from app.modules.platform.regulatory.services.regulatory_resolver import (
    RegulatoryConfigError,
    regulatory_resolver,
)


def _tx_row(tx: dict) -> dict:
    return {
        "party_gstin": tx.get("party_gstin"),
        "invoice_date": tx.get("invoice_date"),
        "taxable_value": float(tx.get("taxable_value") or 0),
        "cgst": float(tx.get("cgst_amount") or 0),
        "sgst": float(tx.get("sgst_amount") or 0),
        "igst": float(tx.get("igst_amount") or 0),
        "source_id": tx.get("source_id"),
        "gst_type": tx.get("gst_type"),
    }


def build_gstr1_payload(
    transactions: list[dict], *, return_period: str, org_id: str | None = None
) -> dict:
    try:
        b2c_large_threshold = regulatory_resolver.resolve_threshold_amount(
            "gst.b2c_large_invoice", org_id=org_id, required=True
        )
    except RegulatoryConfigError as exc:
        raise ValueError(str(exc)) from exc

    b2b: list[dict] = []
    b2c_large: list[dict] = []
    b2c_small_agg: dict[str, float] = {"taxable_value": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0}
    exports: list[dict] = []
    credit_notes: list[dict] = []
    debit_notes: list[dict] = []

    for tx in transactions:
        gst_type = str(tx.get("gst_type") or "")
        if gst_type == "export":
            exports.append(_tx_row(tx))
            continue
        if gst_type == "credit_note":
            credit_notes.append(_tx_row(tx))
            continue
        if gst_type == "debit_note":
            debit_notes.append(_tx_row(tx))
            continue
        if gst_type not in {"sales"}:
            continue

        row = _tx_row(tx)
        party_gstin = str(tx.get("party_gstin") or "").strip()
        taxable = float(tx.get("taxable_value") or 0)

        if party_gstin:
            b2b.append(row)
        elif taxable >= b2c_large_threshold:
            b2c_large.append(row)
        else:
            b2c_small_agg["taxable_value"] += taxable
            b2c_small_agg["cgst"] += float(tx.get("cgst_amount") or 0)
            b2c_small_agg["sgst"] += float(tx.get("sgst_amount") or 0)
            b2c_small_agg["igst"] += float(tx.get("igst_amount") or 0)

    b2c_small = []
    if b2c_small_agg["taxable_value"] > 0:
        b2c_small.append({
            "place_of_supply": "aggregate",
            **{k: round(v, 2) for k, v in b2c_small_agg.items()},
        })

    return {
        "return_type": "GSTR-1",
        "return_period": return_period,
        "b2b": b2b,
        "b2c_large": b2c_large,
        "b2c_small": b2c_small,
        "exports": exports,
        "credit_notes": credit_notes,
        "debit_notes": debit_notes,
        "summary": _summarize(transactions),
    }


def build_gstr3b_payload(
    transactions: list[dict],
    *,
    return_period: str,
    itc_claimed: float = 0,
) -> dict:
    output_tax = sum(
        float(t.get("cgst_amount") or 0) + float(t.get("sgst_amount") or 0) + float(t.get("igst_amount") or 0)
        for t in transactions
        if t.get("gst_type") in {"sales", "debit_note"}
    )
    input_tax = sum(
        float(t.get("cgst_amount") or 0) + float(t.get("sgst_amount") or 0) + float(t.get("igst_amount") or 0)
        for t in transactions
        if t.get("gst_type") in {"purchase", "credit_note", "reverse_charge"}
    )
    exempt_supply = round(
        sum(float(t.get("taxable_value") or 0) for t in transactions if str(t.get("gst_type")) in {"export", "exempt"}),
        2,
    )
    net = round(output_tax - min(itc_claimed, input_tax), 2)
    return {
        "return_type": "GSTR-3B",
        "return_period": return_period,
        "section_3_1_tax_liability": round(output_tax, 2),
        "section_4_itc": round(min(itc_claimed, input_tax), 2),
        "section_5_exempt_supply": exempt_supply,
        "output_tax": round(output_tax, 2),
        "input_tax": round(input_tax, 2),
        "itc_claimed": round(itc_claimed, 2),
        "net_liability": net,
    }


def build_gstr9_payload(transactions: list[dict], *, financial_year: str) -> dict:
    """Annual return summary aggregated from GST transaction ledger."""
    sales = [t for t in transactions if t.get("gst_type") in {"sales", "debit_note"}]
    purchases = [t for t in transactions if t.get("gst_type") in {"purchase", "credit_note", "reverse_charge"}]
    return {
        "return_type": "GSTR-9",
        "financial_year": financial_year,
        "outward_supplies": {
            "count": len(sales),
            "taxable_value": round(sum(float(t.get("taxable_value") or 0) for t in sales), 2),
            "tax": round(
                sum(
                    float(t.get("cgst_amount") or 0) + float(t.get("sgst_amount") or 0) + float(t.get("igst_amount") or 0)
                    for t in sales
                ),
                2,
            ),
        },
        "inward_supplies": {
            "count": len(purchases),
            "taxable_value": round(sum(float(t.get("taxable_value") or 0) for t in purchases), 2),
            "tax": round(
                sum(
                    float(t.get("cgst_amount") or 0) + float(t.get("sgst_amount") or 0) + float(t.get("igst_amount") or 0)
                    for t in purchases
                ),
                2,
            ),
        },
        "exports": {
            "count": len([t for t in transactions if t.get("gst_type") == "export"]),
            "taxable_value": round(
                sum(float(t.get("taxable_value") or 0) for t in transactions if t.get("gst_type") == "export"),
                2,
            ),
        },
        "summary": _summarize(transactions),
    }


def _summarize(transactions: list[dict]) -> dict:
    return {
        "count": len(transactions),
        "taxable_value": round(sum(float(t.get("taxable_value") or 0) for t in transactions), 2),
        "total_tax": round(
            sum(
                float(t.get("cgst_amount") or 0) + float(t.get("sgst_amount") or 0) + float(t.get("igst_amount") or 0)
                for t in transactions
            ),
            2,
        ),
    }
