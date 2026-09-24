from __future__ import annotations

"""Salary TDS under section 192 using DB-configured slabs and deductions."""

from app.modules.platform.regulatory.services.regulatory_resolver import (
    RegulatoryConfigError,
    regulatory_resolver,
)


def compute_annual_tax(
    taxable_income: float,
    *,
    org_id: str | None = None,
    as_of: str | None = None,
    set_code: str | None = None,
) -> float:
    """Compute annual income tax from taxable income using progressive slabs from DB."""
    if taxable_income <= 0:
        return 0.0
    try:
        bands = regulatory_resolver.resolve_slab_bands(
            set_code, org_id=org_id, as_of=as_of
        )
    except RegulatoryConfigError as exc:
        raise ValueError(str(exc)) from exc
    tax = 0.0
    prev_limit = 0.0
    for upper, rate in bands:
        limit = upper if upper is not None else float("inf")
        band = min(taxable_income, limit) - prev_limit
        if band <= 0:
            break
        tax += band * rate
        prev_limit = limit
        if upper is None or taxable_income <= upper:
            break
    # Optional cess
    try:
        cess_pct = regulatory_resolver.resolve_param_numeric(
            "income_tax.health_education_cess_pct",
            org_id=org_id,
            as_of=as_of,
            required=False,
            default=0,
        )
    except RegulatoryConfigError:
        cess_pct = 0
    if cess_pct:
        tax = tax * (1 + float(cess_pct) / 100.0)
    return round(tax, 2)


def compute_monthly_tds(
    *,
    monthly_gross: float,
    months_elapsed_in_fy: int = 1,
    prior_ytd_gross: float = 0.0,
    prior_ytd_tds: float = 0.0,
    other_income_annual: float = 0.0,
    org_id: str | None = None,
    as_of: str | None = None,
) -> dict:
    """
    Estimate monthly TDS using annualized income and DB India FY slab rates.
    months_elapsed_in_fy includes the current month.
    """
    months_elapsed = max(1, min(months_elapsed_in_fy, 12))
    ytd_gross = prior_ytd_gross + monthly_gross
    projected_annual_gross = (ytd_gross / months_elapsed) * 12
    try:
        std = regulatory_resolver.resolve_param_numeric(
            "income_tax.standard_deduction_annual",
            org_id=org_id,
            as_of=as_of,
            required=True,
        )
    except RegulatoryConfigError as exc:
        raise ValueError(str(exc)) from exc
    taxable_annual = max(0.0, projected_annual_gross + other_income_annual - float(std))
    annual_tax = compute_annual_tax(taxable_annual, org_id=org_id, as_of=as_of)
    # Apply 87A rebate where total tax <= rebate (simplified)
    try:
        rebate = regulatory_resolver.resolve_param_numeric(
            "income_tax.rebate_87a_amount",
            org_id=org_id,
            as_of=as_of,
            required=False,
            default=0,
        )
    except RegulatoryConfigError:
        rebate = 0
    if rebate and annual_tax > 0:
        annual_tax = max(0.0, annual_tax - min(annual_tax, float(rebate)))
    remaining_tax = max(0.0, annual_tax - prior_ytd_tds)
    remaining_months = max(1, 12 - months_elapsed + 1)
    monthly_tds = round(remaining_tax / remaining_months, 2)
    return {
        "monthly_gross": monthly_gross,
        "projected_annual_gross": round(projected_annual_gross, 2),
        "taxable_annual_income": round(taxable_annual, 2),
        "annual_tax": annual_tax,
        "monthly_tds": monthly_tds,
        "tds_section": "192",
        "standard_deduction": float(std),
    }
