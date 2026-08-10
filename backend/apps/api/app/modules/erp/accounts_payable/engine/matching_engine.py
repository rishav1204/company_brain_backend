from __future__ import annotations

import warnings

DEFAULT_TOLERANCE = 0.01


def three_way_match(*, po_amount: float, grn_amount: float, invoice_amount: float, tolerance: float = DEFAULT_TOLERANCE) -> dict:
    warnings.warn(
        "matching_engine.three_way_match is deprecated; use procurement.services.matching_service",
        DeprecationWarning,
        stacklevel=2,
    )
    po_var = abs(invoice_amount - po_amount)
    grn_var = abs(invoice_amount - grn_amount)
    ok = po_var <= tolerance and grn_var <= tolerance
    return {
        "matched": ok,
        "po_variance": round(invoice_amount - po_amount, 2),
        "grn_variance": round(invoice_amount - grn_amount, 2),
        "tolerance": tolerance,
        "requires_escalation": not ok,
        "deprecated": True,
    }
