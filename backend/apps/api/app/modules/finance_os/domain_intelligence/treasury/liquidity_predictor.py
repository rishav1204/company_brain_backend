from __future__ import annotations

from app.modules.erp.query_services import domain_calc


def forecast_liquidity(*, inflows: list[dict], outflows: list[dict]) -> dict:
    buckets = domain_calc.bucket_cashflows(inflows=inflows, outflows=outflows)
    shortage = [k for k, v in buckets["buckets"].items() if v["net"] < 0]
    return {
        **buckets,
        "shortage_buckets": shortage,
        "risk_level": "high" if "7d" in shortage else ("medium" if "30d" in shortage else "low"),
    }
