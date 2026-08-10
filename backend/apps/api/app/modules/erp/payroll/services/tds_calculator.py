from __future__ import annotations

"""India new tax regime slabs (FY basic slabs) for salary TDS under section 192."""

# (upper_limit_exclusive, marginal_rate) — progressive slabs on annual taxable income
INDIA_FY_SLABS: list[tuple[float, float]] = [
    (400_000, 0.0),
    (800_000, 0.05),
    (1_200_000, 0.10),
    (1_600_000, 0.15),
    (2_000_000, 0.20),
    (2_400_000, 0.25),
    (float("inf"), 0.30),
]

STANDARD_DEDUCTION_ANNUAL = 75_000.0


def compute_annual_tax(taxable_income: float) -> float:
    """Compute annual income tax from taxable income using progressive slabs."""
    if taxable_income <= 0:
        return 0.0
    tax = 0.0
    prev_limit = 0.0
    for upper, rate in INDIA_FY_SLABS:
        band = min(taxable_income, upper) - prev_limit
        if band <= 0:
            break
        tax += band * rate
        prev_limit = upper
    return round(tax, 2)


def compute_monthly_tds(
    *,
    monthly_gross: float,
    months_elapsed_in_fy: int = 1,
    prior_ytd_gross: float = 0.0,
    prior_ytd_tds: float = 0.0,
    other_income_annual: float = 0.0,
) -> dict:
    """
    Estimate monthly TDS using annualized income and India FY slab rates.
    months_elapsed_in_fy includes the current month.
    """
    months_elapsed = max(1, min(months_elapsed_in_fy, 12))
    ytd_gross = prior_ytd_gross + monthly_gross
    projected_annual_gross = (ytd_gross / months_elapsed) * 12
    taxable_annual = max(0.0, projected_annual_gross + other_income_annual - STANDARD_DEDUCTION_ANNUAL)
    annual_tax = compute_annual_tax(taxable_annual)
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
    }
