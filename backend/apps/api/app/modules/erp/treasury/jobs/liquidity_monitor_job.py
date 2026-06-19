from __future__ import annotations

from app.modules.erp.treasury.services.liquidity_service import liquidity_service


def run_liquidity_monitor(org_id: str) -> dict:
    alerts = liquidity_service.monitor_and_alert(org_id)
    return {"alerts_created": len(alerts)}
