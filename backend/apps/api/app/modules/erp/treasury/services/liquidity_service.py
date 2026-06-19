from __future__ import annotations

from app.modules.erp.banking.repositories.bank_account_repository import bank_account_repository
from app.modules.erp.treasury.engine.liquidity_engine import bucket_cashflows, compute_coverage_ratio
from app.modules.erp.treasury.engine.risk_engine import coverage_health_band, detect_treasury_risks
from app.modules.erp.treasury.events.treasury_events import emit_liquidity_alert_created, emit_treasury_risk_detected
from app.modules.erp.treasury.repositories.liquidity_alert_repository import liquidity_alert_repository
from app.modules.erp.treasury.services.cash_position_service import cash_position_service
from app.modules.erp.treasury.services.treasury_forecast_service import treasury_forecast_service


class LiquidityService:
    def total_obligations(self, org_id: str) -> float:
        position = cash_position_service.compute_live_position(org_id)
        return float(position.get("upcoming_payments") or 0) + sum(
            float(o.get("amount") or 0) for o in treasury_forecast_service.collect_outflows(org_id)
            if str(o.get("source")) == "compliance"
        )

    def analyze(self, org_id: str) -> dict:
        position = cash_position_service.compute_live_position(org_id)
        available = float(position.get("available_cash") or 0)
        obligations = self.total_obligations(org_id)
        coverage = compute_coverage_ratio(available_cash=available, total_obligations=obligations)
        band = coverage_health_band(coverage if coverage < 900 else 2.0)
        inflows = treasury_forecast_service.collect_inflows(org_id)
        outflows = treasury_forecast_service.collect_outflows(org_id)
        buckets = bucket_cashflows(inflows=inflows, outflows=outflows)
        shortage = [k for k, v in buckets["buckets"].items() if v["net"] < 0]
        forecast_30 = treasury_forecast_service.build_forecast(org_id, horizon_days=30)
        risks = detect_treasury_risks(
            forecast_balance=float(forecast_30.get("forecast_cash_balance") or 0),
            coverage_ratio=coverage if coverage < 900 else 2.0,
            upcoming_tax=sum(float(o.get("amount") or 0) for o in outflows if o.get("source") == "compliance"),
        )
        return {
            **buckets,
            "available_cash": available,
            "total_obligations": round(obligations, 2),
            "liquidity_coverage": coverage if coverage < 900 else None,
            "health_band": band,
            "shortage_buckets": shortage,
            "risk_level": "high" if band == "risk" else ("medium" if band == "monitor" else "low"),
            "risks": risks,
            "forecast_30d": forecast_30,
        }

    def monitor_and_alert(self, org_id: str) -> list[dict]:
        analysis = self.analyze(org_id)
        created = []
        band = analysis.get("health_band")
        if band == "risk":
            row = liquidity_alert_repository.create(
                org_id,
                alert_type="liquidity_risk",
                severity="high",
                message=f"Liquidity coverage in risk band ({analysis.get('liquidity_coverage')})",
            )
            emit_liquidity_alert_created(org_id, alert_id=str(row["id"]), alert_type="liquidity_risk", severity="high")
            created.append(row)
        elif band == "monitor":
            row = liquidity_alert_repository.create(
                org_id,
                alert_type="liquidity_monitor",
                severity="medium",
                message="Liquidity coverage in monitor band — review upcoming obligations",
            )
            emit_liquidity_alert_created(org_id, alert_id=str(row["id"]), alert_type="liquidity_monitor", severity="medium")
            created.append(row)
        for risk in analysis.get("risks") or []:
            emit_treasury_risk_detected(org_id, risk_type=risk["type"], severity=risk["severity"], message=risk["message"])
        return created

    def list_alerts(self, org_id: str, *, status: str | None = "open") -> list[dict]:
        return liquidity_alert_repository.list(org_id, status=status)

    def acknowledge_alert(self, org_id: str, *, alert_id: str, acknowledged_by: str) -> dict:
        return liquidity_alert_repository.acknowledge(org_id, alert_id=alert_id, acknowledged_by=acknowledged_by)

    def forecast(self, org_id: str) -> dict:
        analysis = self.analyze(org_id)
        cf = treasury_forecast_service.build_forecast(org_id, horizon_days=180)
        return {**analysis, "cashflow": cf}


liquidity_service = LiquidityService()
