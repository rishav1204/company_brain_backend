from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.treasury.engine.liquidity_engine import bucket_cashflows


def forecast_liquidity(*, inflows: list[dict], outflows: list[dict]) -> dict:
    buckets = bucket_cashflows(inflows=inflows, outflows=outflows)
    shortage = [k for k, v in buckets["buckets"].items() if v["net"] < 0]
    return {
        **buckets,
        "shortage_buckets": shortage,
        "risk_level": "high" if "7d" in shortage else ("medium" if "30d" in shortage else "low"),
    }
