from __future__ import annotations

from app.core.config import settings
from app.modules.erp.payroll.repositories.employee_repository import employee_repository
from app.modules.erp.payroll.repositories.salary_run_repository import salary_run_repository
from app.modules.erp.payroll.services.tds_calculator import compute_monthly_tds
from app.modules.erp.security.company_resolution_service import company_resolution_service
from app.modules.erp.security.company_scope import require_company_id_for_erp_write
from app.modules.erp.tax.repositories.compliance_repository import tds_transaction_repository


def _financial_year_from_period(return_period: str) -> str:
    """Return period YYYY-MM -> financial year label e.g. 2025-26 for Apr-Mar."""
    year = int(return_period[:4])
    month = int(return_period[5:7]) if len(return_period) >= 7 else 4
    if month >= 4:
        return f"{year}-{str(year + 1)[-2:]}"
    return f"{year - 1}-{str(year)[-2:]}"


def _months_elapsed_in_fy(return_period: str) -> int:
    month = int(return_period[5:7]) if len(return_period) >= 7 else 4
    if month >= 4:
        return month - 3
    return month + 9


class SalaryRunService:
    def create_employee(
        self,
        org_id: str,
        *,
        employee_code: str,
        pan: str,
        name: str,
        date_of_joining: str | None = None,
        company_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        if len(pan.strip()) != 10:
            raise ValueError("PAN must be 10 characters")
        if settings.erp_require_company_id:
            company_id = company_resolution_service.resolve_for_write(
                org_id, company_id=company_id, operation="payroll.employee.create"
            )
        elif company_id:
            require_company_id_for_erp_write(
                org_id=org_id, company_id=company_id, operation="payroll.employee.create"
            )
        return employee_repository.create(
            org_id,
            employee_code=employee_code,
            pan=pan,
            name=name,
            date_of_joining=date_of_joining,
            company_id=company_id,
            metadata=metadata,
        )

    def get_employee(self, org_id: str, *, employee_id: str) -> dict:
        row = employee_repository.get(org_id, employee_id=employee_id)
        if not row:
            raise ValueError("Employee not found")
        return row

    def list_employees(self, org_id: str, *, status: str | None = "active") -> list[dict]:
        return employee_repository.list(org_id, status=status)

    def update_employee(
        self,
        org_id: str,
        *,
        employee_id: str,
        name: str | None = None,
        pan: str | None = None,
        date_of_joining: str | None = None,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        if pan is not None and len(pan.strip()) != 10:
            raise ValueError("PAN must be 10 characters")
        row = employee_repository.update(
            org_id,
            employee_id=employee_id,
            name=name,
            pan=pan,
            date_of_joining=date_of_joining,
            status=status,
            metadata=metadata,
        )
        if not row:
            raise ValueError("Employee not found")
        return row

    def run_salary(
        self,
        org_id: str,
        *,
        employee_id: str,
        return_period: str,
        gross_salary: float,
        payment_date: str | None = None,
        challan_number: str | None = None,
        prior_ytd_gross: float | None = None,
        prior_ytd_tds: float | None = None,
        other_income_annual: float = 0.0,
        actor_id: str | None = None,
    ) -> dict:
        if gross_salary <= 0:
            raise ValueError("Gross salary must be positive")
        employee = employee_repository.get(org_id, employee_id=employee_id)
        if not employee:
            raise ValueError("Employee not found")
        if str(employee.get("status")) != "active":
            raise ValueError("Employee is not active")

        company_id = employee.get("company_id")
        fy = _financial_year_from_period(return_period)
        months_elapsed = _months_elapsed_in_fy(return_period)

        if prior_ytd_gross is None or prior_ytd_tds is None:
            prior_runs = salary_run_repository.list(
                org_id, return_period=None, employee_id=employee_id, limit=12
            )
            fy_prefix = fy.split("-")[0]
            prior_period_runs = [
                r for r in prior_runs
                if str(r.get("return_period") or "").startswith(fy_prefix)
                and str(r.get("return_period") or "") < return_period
            ]
            prior_ytd_gross = prior_ytd_gross if prior_ytd_gross is not None else sum(
                float(r.get("gross_salary") or 0) for r in prior_period_runs
            )
            prior_ytd_tds = prior_ytd_tds if prior_ytd_tds is not None else sum(
                float(r.get("tds_amount") or 0) for r in prior_period_runs
            )

        tds_calc = compute_monthly_tds(
            monthly_gross=gross_salary,
            months_elapsed_in_fy=months_elapsed,
            prior_ytd_gross=float(prior_ytd_gross or 0),
            prior_ytd_tds=float(prior_ytd_tds or 0),
            other_income_annual=other_income_annual,
        )

        run = salary_run_repository.create(
            org_id,
            employee_id=employee_id,
            return_period=return_period,
            gross_salary=gross_salary,
            tds_amount=tds_calc["monthly_tds"],
            tds_section=tds_calc["tds_section"],
            company_id=company_id,
            challan_number=challan_number,
            payment_date=payment_date,
            status="calculated",
            metadata={
                "tds_calculation": tds_calc,
                "financial_year": fy,
                "processed_by": actor_id,
            },
        )

        tds_transaction_repository.create(
            org_id,
            source_type="payroll_salary_run",
            source_id=str(run["id"]),
            section_code="192",
            gross_amount=gross_salary,
            tds_amount=tds_calc["monthly_tds"],
            net_amount=round(gross_salary - tds_calc["monthly_tds"], 2),
            status="calculated",
            return_period=return_period,
            deduction_date=payment_date,
            metadata={
                "employee_id": employee_id,
                "employee_code": employee.get("employee_code"),
                "pan": employee.get("pan"),
                "salary_run_id": run["id"],
            },
        )

        return {**run, "employee": employee, "tds_calculation": tds_calc}

    def get_salary_run(self, org_id: str, *, run_id: str) -> dict:
        row = salary_run_repository.get(org_id, run_id=run_id)
        if not row:
            raise ValueError("Salary run not found")
        return row

    def list_salary_runs(
        self,
        org_id: str,
        *,
        return_period: str | None = None,
        employee_id: str | None = None,
    ) -> list[dict]:
        return salary_run_repository.list(org_id, return_period=return_period, employee_id=employee_id)


salary_run_service = SalaryRunService()
