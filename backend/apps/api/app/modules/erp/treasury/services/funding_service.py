from __future__ import annotations

from app.modules.erp.treasury.services.cash_position_service import cash_position_service
from app.modules.erp.treasury.services.liquidity_service import liquidity_service
from app.modules.erp.treasury.services.treasury_forecast_service import treasury_forecast_service


class FundingService:
    def funding_requirement(self, org_id: str) -> dict:
        position = cash_position_service.compute_live_position(org_id)
        forecast_30 = treasury_forecast_service.build_forecast(org_id, horizon_days=30)
        available = float(position.get("available_cash") or 0)
        projected = float(forecast_30.get("forecast_cash_balance") or 0)
        deficit = max(0.0, -projected)
        return {
            "available_cash": available,
            "projected_30d": projected,
            "funding_required": round(deficit, 2),
            "net_liquidity": position.get("net_liquidity"),
        }


class DashboardService:
    def build(self, org_id: str) -> dict:
        position = cash_position_service.compute_live_position(org_id)
        liquidity = liquidity_service.analyze(org_id)
        forecasts = treasury_forecast_service.list_stored(org_id) or treasury_forecast_service.refresh_all(org_id)
        alerts = liquidity_service.list_alerts(org_id, status="open")
        from app.modules.erp.treasury.services.concentration_service import concentration_service

        funding = funding_service.funding_requirement(org_id)
        return {
            "cash_position": position,
            "liquidity": liquidity,
            "forecasts": forecasts[:5],
            "alerts": alerts,
            "bank_concentration": concentration_service.bank_concentration(org_id),
            "vendor_concentration": concentration_service.vendor_concentration(org_id),
            "funding": funding,
        }


funding_service = FundingService()
dashboard_service = DashboardService()
