from __future__ import annotations

from datetime import date

from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository
from app.modules.erp.fiscal.repositories.fiscal_year_repository import fiscal_year_repository


def _fy_code(start: date) -> str:
    end_year = start.year + 1 if start.month >= 4 else start.year
    start_yy = start.year % 100
    end_yy = end_year % 100
    return f"FY{start.year}-{end_yy:02d}" if start.month >= 4 else f"FY{start.year - 1}-{start_yy:02d}"


class FiscalYearService:
    def create_fiscal_year(
        self,
        org_id: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        fiscal_year_code: str | None = None,
        company_id: str | None = None,
        set_current: bool = True,
        generate_periods: bool = True,
    ) -> dict:
        if not start_date:
            today = date.today()
            year = today.year if today.month >= 4 else today.year - 1
            start = date(year, 4, 1)
            end = date(year + 1, 3, 31)
            start_date = start.isoformat()
            end_date = end.isoformat()
        if not fiscal_year_code:
            fiscal_year_code = _fy_code(date.fromisoformat(start_date[:10]))
        row = fiscal_year_repository.create(
            org_id,
            fiscal_year_code=fiscal_year_code,
            start_date=start_date,
            end_date=end_date,
            company_id=company_id,
            is_current=set_current,
        )
        periods = []
        if generate_periods:
            periods = self._generate_monthly_periods(org_id, fiscal_year_id=str(row["id"]), start_date=start_date, company_id=company_id)
        return {**row, "periods_generated": len(periods)}

    def list_fiscal_years(self, org_id: str, *, company_id: str | None = None) -> list[dict]:
        return fiscal_year_repository.list(org_id, company_id=company_id)

    def get_fiscal_year(self, org_id: str, *, fiscal_year_id: str) -> dict:
        row = fiscal_year_repository.get(org_id, fiscal_year_id=fiscal_year_id)
        if not row:
            raise ValueError("Fiscal year not found")
        return row

    def _generate_monthly_periods(self, org_id: str, *, fiscal_year_id: str, start_date: str, company_id: str | None) -> list[dict]:
        from calendar import monthrange
        from datetime import timedelta

        periods = []
        y, m, _ = [int(x) for x in start_date[:10].split("-")]
        for n in range(1, 13):
            last_day = monthrange(y, m)[1]
            period_start = date(y, m, 1)
            period_end = date(y, m, last_day)
            periods.append(
                fiscal_period_repository.create(
                    org_id,
                    fiscal_year_id=fiscal_year_id,
                    period_name=period_start.strftime("%b %Y"),
                    period_number=n,
                    start_date=period_start.isoformat(),
                    end_date=period_end.isoformat(),
                    company_id=company_id,
                )
            )
            m += 1
            if m > 12:
                m = 1
                y += 1
        return periods


fiscal_year_service = FiscalYearService()
