from __future__ import annotations

from app.modules.erp.query_services import treasury_queries


def load_treasury(org_id: str) -> dict:
    position = treasury_queries.compute_live_position(org_id)
    liquidity = treasury_queries.analyze_liquidity(org_id)
    available = float(position.get("available_cash") or position.get("net_liquidity") or 0)
    coverage = liquidity.get("liquidity_coverage")
    return {
        "available_cash": available,
        "liquidity_coverage": float(coverage) if coverage is not None else None,
        "health_band": liquidity.get("health_band"),
        "total_obligations": float(liquidity.get("total_obligations") or 0),
        "position": position,
    }
