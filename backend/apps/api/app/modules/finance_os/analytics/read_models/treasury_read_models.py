from __future__ import annotations


def load_treasury(org_id: str) -> dict:
    from app.modules.erp.treasury.services.cash_position_service import cash_position_service
    from app.modules.erp.treasury.services.liquidity_service import liquidity_service

    position = cash_position_service.compute_live_position(org_id)
    liquidity = liquidity_service.analyze(org_id)
    available = float(position.get("available_cash") or position.get("net_liquidity") or 0)
    coverage = liquidity.get("liquidity_coverage")
    return {
        "available_cash": available,
        "liquidity_coverage": float(coverage) if coverage is not None else None,
        "health_band": liquidity.get("health_band"),
        "total_obligations": float(liquidity.get("total_obligations") or 0),
        "position": position,
    }
