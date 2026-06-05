from __future__ import annotations



from app.modules.erp.journals.repositories.accrual_repository import accrual_repository
from app.modules.erp.journals.services.approval_service import approval_service
from app.modules.erp.journals.services.journal_service import journal_service





def compute_accrual_amount(*, estimated_expense: float, paid_amount: float = 0) -> float:

    """AccruedExpense = EstimatedExpense - PaidAmount"""

    amount = float(estimated_expense) - float(paid_amount)

    if amount <= 0:

        raise ValueError("Accrual amount must be positive (estimated_expense must exceed paid_amount)")

    return amount





class AccrualService:

    def create_accrual(

        self,

        org_id: str,

        *,

        accrual_type: str,

        accrual_date: str,

        expense_account_id: str,

        liability_account_id: str,

        amount: float | None = None,

        estimated_expense: float | None = None,

        paid_amount: float = 0,

        source_reference: str | None = None,

        reversal_date: str | None = None,

        company_id: str | None = None,

        created_by: str | None = None,

    ) -> dict:

        if amount is None:

            if estimated_expense is None:

                raise ValueError("Provide amount or estimated_expense")

            amount = compute_accrual_amount(estimated_expense=estimated_expense, paid_amount=paid_amount)

        elif amount <= 0:

            raise ValueError("Accrual amount must be positive")



        lines = [

            {

                "account_id": expense_account_id,

                "debit_amount": amount,

                "credit_amount": 0,

                "line_description": f"Accrual expense ({accrual_type})",

            },

            {

                "account_id": liability_account_id,

                "debit_amount": 0,

                "credit_amount": amount,

                "line_description": f"Accrual liability ({accrual_type})",

            },

        ]

        journal = journal_service.create_draft(

            org_id,

            created_by=created_by,

            journal_type="accrual",

            posting_date=accrual_date,

            description=f"Accrual entry: {accrual_type}",

            source_type="accrual",

            source_id=source_reference,

            company_id=company_id,

            lines=lines,

        )

        jid = str(journal["journal"]["id"])

        accrual = accrual_repository.create(

            org_id,

            accrual_type=accrual_type,

            accrual_date=accrual_date,

            amount=amount,

            source_reference=source_reference,

            reversal_date=reversal_date,

            journal_id=jid,

            company_id=company_id,

            metadata={

                "expense_account_id": expense_account_id,

                "liability_account_id": liability_account_id,

                "estimated_expense": estimated_expense,

                "paid_amount": paid_amount,

            },

        )

        return {"accrual": accrual, "journal": journal, "computed_amount": amount}



    def list_accruals(self, org_id: str) -> list[dict]:

        return accrual_repository.list(org_id)



    def process_due_reversals(self, org_id: str, *, as_of_date: str | None = None) -> list[dict]:

        from datetime import date



        run_date = as_of_date or date.today().isoformat()

        due = accrual_repository.list_due_reversals(org_id, as_of_date=run_date)

        results: list[dict] = []

        for entry in due:

            meta = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}

            expense_id = str(meta.get("expense_account_id") or "")

            liability_id = str(meta.get("liability_account_id") or "")

            amount = float(entry.get("amount") or 0)

            if not expense_id or not liability_id or amount <= 0:

                continue

            lines = [

                {

                    "account_id": liability_id,

                    "debit_amount": amount,

                    "credit_amount": 0,

                    "line_description": f"Accrual reversal liability ({entry.get('accrual_type')})",

                },

                {

                    "account_id": expense_id,

                    "debit_amount": 0,

                    "credit_amount": amount,

                    "line_description": f"Accrual reversal expense ({entry.get('accrual_type')})",

                },

            ]

            journal = journal_service.create_draft(

                org_id,

                created_by=None,

                journal_type="accrual",

                posting_date=run_date,

                description=f"Accrual reversal: {entry.get('accrual_type')}",

                source_type="accrual_reversal",

                source_id=str(entry.get("id")),

                company_id=entry.get("company_id"),

                lines=lines,

                idempotency_key=f"accrual-reversal:{entry['id']}:{run_date}",

            )

            reversal_jid = str(journal["journal"]["id"])

            # Blueprint: draft → approval workflow → posting (maker-checker safe).
            try:
                approval_service.submit_for_approval(org_id, journal_id=reversal_jid, actor_id=None)
            except Exception:
                pass
            try:
                from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

                handle_entity_created(
                    org_id=org_id,
                    payload={
                        "entity_type": "journal",
                        "entity_id": reversal_jid,
                        "event": "scheduler.tick",
                        "metadata": {
                            "journal_id": reversal_jid,
                            "source": "accrual_reversal",
                            "accrual_id": str(entry.get("id") or ""),
                            "run_date": run_date,
                        },
                    },
                )
            except Exception:
                pass

            accrual_repository.mark_reversed(org_id, accrual_id=str(entry["id"]), reversal_journal_id=reversal_jid)

            results.append({"accrual_id": entry["id"], "reversal_journal_id": reversal_jid})

        return results





accrual_service = AccrualService()


