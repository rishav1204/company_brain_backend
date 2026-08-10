from __future__ import annotations



from uuid import uuid4



from app.modules.erp.payroll.repositories.salary_run_repository import salary_run_repository

from app.modules.erp.tax.repositories.compliance_repository import tds_transaction_repository





class PayrollTdsService:

    """Ingest salary TDS from payroll salary runs and treasury payment requests for 24Q."""



    def sync_from_salary_runs(self, org_id: str, *, return_period: str) -> list[dict]:

        created: list[dict] = []

        for run in salary_run_repository.list(org_id, return_period=return_period, limit=5000):

            gross = float(run.get("gross_salary") or 0)

            tds = float(run.get("tds_amount") or 0)

            if gross <= 0:

                continue

            row = tds_transaction_repository.create(

                org_id,

                source_type="payroll_salary_run",

                source_id=str(run.get("id") or uuid4()),

                section_code=str(run.get("tds_section") or "192"),

                gross_amount=gross,

                tds_amount=tds,

                net_amount=round(gross - tds, 2),

                status="calculated",

                return_period=return_period,

                deduction_date=str(run.get("payment_date") or "")[:10] or None,

                metadata={

                    "employee_id": run.get("employee_id"),

                    "employee_code": run.get("employee_code"),

                    "pan": run.get("pan"),

                    "employee_name": run.get("employee_name"),

                    "salary_run_id": run.get("id"),

                },

            )

            created.append(row)

        return created



    def sync_from_payment_requests(self, org_id: str, *, return_period: str) -> list[dict]:

        from app.modules.erp.banking.repositories.payment_request_repository import payment_request_repository



        created: list[dict] = []

        for pr in payment_request_repository.list_by_types(org_id, payment_types=["salary", "payroll"]):

            sched = str(pr.get("scheduled_date") or pr.get("payment_date") or "")[:7]

            if sched and sched != return_period[:7]:

                continue

            gross = float(pr.get("gross_amount") or pr.get("amount") or 0)

            tds = float(pr.get("tds_amount") or pr.get("tax_withheld") or 0)

            if tds <= 0 and gross <= 0:

                continue

            if tds <= 0:

                tds = round(gross * 0.10, 2)

            meta = pr.get("metadata") if isinstance(pr.get("metadata"), dict) else {}

            row = tds_transaction_repository.create(

                org_id,

                source_type="payroll",

                source_id=str(pr.get("id") or uuid4()),

                section_code=str(meta.get("tds_section") or "192"),

                gross_amount=gross,

                tds_amount=tds,

                net_amount=round(gross - tds, 2),

                status="calculated",

                return_period=return_period,

                deduction_date=str(pr.get("scheduled_date") or pr.get("payment_date") or "")[:10] or None,

                metadata={"employee_id": meta.get("employee_id"), "payment_request_id": pr.get("id")},

            )

            created.append(row)

        return created



    def sync_all(self, org_id: str, *, return_period: str) -> dict:

        salary_rows = self.sync_from_salary_runs(org_id, return_period=return_period)

        payment_rows = self.sync_from_payment_requests(org_id, return_period=return_period)

        return {

            "return_period": return_period,

            "salary_run_transactions": len(salary_rows),

            "payment_request_transactions": len(payment_rows),

            "total": len(salary_rows) + len(payment_rows),

        }





payroll_tds_service = PayrollTdsService()

