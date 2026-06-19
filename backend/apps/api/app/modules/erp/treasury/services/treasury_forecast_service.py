from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.treasury.engine.forecast_engine import STANDARD_HORIZONS, forecast_all_horizons, forecast_balance
from app.modules.erp.treasury.events.treasury_events import emit_cash_forecast_updated
from app.modules.erp.treasury.repositories.forecast_repository import forecast_repository
from app.modules.erp.treasury.services.cash_position_service import cash_position_service
from app.modules.erp.treasury.services.cashflow_service import cashflow_service


class TreasuryForecastService:
    def collect_inflows(self, org_id: str) -> list[dict]:
        return cashflow_service._collect_inflows(org_id)

    def collect_outflows(self, org_id: str) -> list[dict]:
        items = cashflow_service._collect_outflows(org_id)
        items.extend(self._compliance_obligations(org_id))
        return items

    def _compliance_obligations(self, org_id: str) -> list[dict]:
        items: list[dict] = []
        try:
            from app.modules.erp.compliance.repositories.compliance_repository import compliance_repository

            through = (date.today() + timedelta(days=180)).isoformat()
            for ob in compliance_repository.list(org_id, to_date=through, limit=200):
                if str(ob.get("status")) in {"completed", "waived"}:
                    continue
                due = str(ob.get("due_date") or "")[:10]
                if due and due <= through:
                    items.append({
                        "date": due,
                        "amount": float(ob.get("estimated_amount") or ob.get("amount") or 0) or 1000.0,
                        "source": "compliance",
                    })
        except Exception:
            pass
        return items

    def build_forecast(self, org_id: str, *, horizon_days: int = 30) -> dict:
        position = cash_position_service.compute_live_position(org_id)
        closing = float(position.get("available_cash") or 0)
        inflows = self.collect_inflows(org_id)
        outflows = self.collect_outflows(org_id)
        return forecast_balance(current_closing=closing, inflows=inflows, outflows=outflows, horizon_days=horizon_days)

    def refresh_all(self, org_id: str) -> list[dict]:
        position = cash_position_service.compute_live_position(org_id)
        closing = float(position.get("available_cash") or 0)
        inflows = self.collect_inflows(org_id)
        outflows = self.collect_outflows(org_id)
        saved = []
        for fc in forecast_all_horizons(current_closing=closing, inflows=inflows, outflows=outflows):
            row = forecast_repository.save(org_id, forecast=fc)
            saved.append({**fc, "id": row.get("id")})
            emit_cash_forecast_updated(org_id, horizon_days=fc["horizon_days"], forecast_cash_balance=fc["forecast_cash_balance"])
        return saved

    def list_stored(self, org_id: str, *, horizon_days: int | None = None) -> list[dict]:
        return forecast_repository.list_latest(org_id, horizon_days=horizon_days)


treasury_forecast_service = TreasuryForecastService()
