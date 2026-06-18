from __future__ import annotations

from datetime import date


class RevenueRecognitionService:
    def build_schedule(
        self,
        *,
        contract_value: float,
        contract_months: int,
        start_date: str,
    ) -> dict:
        if contract_months <= 0:
            raise ValueError("contract_months must be positive")
        monthly = round(float(contract_value) / contract_months, 2)
        return {
            "contract_value": contract_value,
            "contract_months": contract_months,
            "monthly_revenue": monthly,
            "start_date": start_date,
            "recognition_method": "straight_line",
            "formula": "MonthlyRevenue = ContractValue / ContractMonths",
        }

    def recognized_to_date(self, schedule: dict, *, as_of: str | None = None) -> float:
        start = date.fromisoformat(str(schedule.get("start_date"))[:10])
        ref = date.fromisoformat((as_of or date.today().isoformat())[:10])
        months_elapsed = max(0, (ref.year - start.year) * 12 + (ref.month - start.month))
        months_elapsed = min(months_elapsed, int(schedule.get("contract_months") or 0))
        return round(float(schedule.get("monthly_revenue") or 0) * months_elapsed, 2)


revenue_recognition_service = RevenueRecognitionService()
