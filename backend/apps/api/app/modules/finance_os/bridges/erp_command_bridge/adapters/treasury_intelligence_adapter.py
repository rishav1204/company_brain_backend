from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import TreasuryIntelligencePort


class TreasuryIntelligenceAdapter:
    """Finance OS implementation of ERP TreasuryIntelligencePort — advisory only."""

    def forecast_cashflow(self, *, inflows: list[dict], outflows: list[dict], horizon_days: int = 30) -> dict:
        from app.modules.finance_os.domain_intelligence.treasury.cashflow_forecaster import forecast_cashflow

        return forecast_cashflow(inflows=inflows, outflows=outflows, horizon_days=horizon_days)

    def forecast_liquidity(self, *, inflows: list[dict], outflows: list[dict]) -> dict:
        from app.modules.finance_os.domain_intelligence.treasury.liquidity_predictor import forecast_liquidity

        return forecast_liquidity(inflows=inflows, outflows=outflows)

    def detect_cash_risks(self, **kwargs) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.treasury.cash_risk_detector import detect_cash_risks

        return detect_cash_risks(**kwargs)

    def detect_surplus_cash(self, *, accounts: list[dict], avg_daily_outflow: float) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.treasury.surplus_cash_detector import detect_surplus_cash

        return detect_surplus_cash(accounts=accounts, avg_daily_outflow=avg_daily_outflow)

    def advise_treasury(self, *, liquidity: dict, position: dict) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.treasury.treasury_advisor import advise_treasury

        return advise_treasury(liquidity=liquidity, position=position)

    def answer_treasury_question(self, *, question: str, position: dict, liquidity: dict) -> dict:
        from app.modules.finance_os.domain_intelligence.treasury.treasury_copilot import answer_treasury_question

        return answer_treasury_question(question=question, position=position, liquidity=liquidity)

    def detect_payment_anomalies(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.payments.anomaly_detector import detect_scheduling_anomalies

        return detect_scheduling_anomalies(**kwargs)


_: TreasuryIntelligencePort | None = None
