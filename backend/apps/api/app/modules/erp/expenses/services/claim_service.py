from __future__ import annotations

from datetime import datetime, timezone

from app.modules.erp.accounts_payable.engine.account_resolver import resolve_expense_account
from app.modules.erp.expenses.engine.account_resolver import resolve_employee_payable_account
from app.modules.erp.expenses.repositories.claim_repository import claim_repository
from app.modules.erp.expenses.services.duplicate_detection_service import duplicate_detection_service
from app.modules.erp.expenses.services.policy_service import expense_policy_service
from app.modules.erp.expenses.validators.claim_validator import (
    ensure_approvable,
    ensure_cancellable,
    ensure_submittable,
)
from app.modules.erp.expenses.workflows.claim_approval_workflow import workflow_metadata
from app.modules.erp.expenses.events.expense_events import emit_claim_approved, emit_claim_created, emit_claim_rejected
from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.services.db import get_db_conn, set_rls_org


class ClaimService:
    def _claim_number(self) -> str:
        return f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def _audit(self, org_id: str, *, action: str, claim_id: str, actor_id: str | None, details: dict) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id, actor_id=actor_id, action=action,
                resource_type="expense_claim", resource_id=claim_id, details=details,
            )
        except Exception:
            pass

    def create(
        self,
        org_id: str,
        *,
        employee_id: str,
        claim_date: str | None = None,
        expense_category: str | None = None,
        company_id: str | None = None,
        cost_center_id: str | None = None,
        department_id: str | None = None,
        created_by: str | None = None,
        items: list[dict] | None = None,
    ) -> dict:
        claim = claim_repository.create(
            org_id,
            claim_number=self._claim_number(),
            employee_id=employee_id,
            claim_date=claim_date,
            expense_category=expense_category,
            company_id=company_id,
            cost_center_id=cost_center_id,
            department_id=department_id,
            created_by=created_by or employee_id,
        )
        claim_id = str(claim["id"])
        for item in items or []:
            expense_account_id = item.get("expense_account_id") or resolve_expense_account(org_id)
            claim_repository.add_item(
                org_id,
                claim_id=claim_id,
                expense_date=str(item.get("expense_date") or claim_date or datetime.now(timezone.utc).date().isoformat())[:10],
                expense_type=str(item.get("expense_type") or "miscellaneous"),
                amount=float(item.get("amount") or 0),
                merchant_name=item.get("merchant_name"),
                description=item.get("description"),
                gst_amount=float(item.get("gst_amount") or 0),
                receipt_id=item.get("receipt_id"),
                expense_account_id=expense_account_id,
            )
        claim = self.get(org_id, claim_id=claim_id)
        emit_claim_created(org_id, claim_id=claim_id, claim_number=str(claim.get("claim_number")), amount=float(claim.get("total_amount") or 0))
        self._audit(org_id, action="expense.claim.created", claim_id=claim_id, actor_id=created_by, details={})
        return claim

    def get(self, org_id: str, *, claim_id: str) -> dict | None:
        claim = claim_repository.get(org_id, claim_id=claim_id)
        if claim:
            claim["items"] = claim_repository.list_items(org_id, claim_id=claim_id)
        return claim

    def list(self, org_id: str, *, employee_id: str | None = None, status: str | None = None) -> list[dict]:
        return claim_repository.list(org_id, employee_id=employee_id, status=status)

    def submit(self, org_id: str, *, claim_id: str, actor_id: str) -> dict:
        claim = claim_repository.get(org_id, claim_id=claim_id)
        if not claim:
            raise ValueError("Claim not found")
        ensure_submittable(str(claim.get("status")))
        items = claim_repository.list_items(org_id, claim_id=claim_id)
        if not items:
            raise ValueError("Claim must have at least one item")
        violations = expense_policy_service.validate_claim(org_id, claim_id=claim_id, items=items)
        hard = [v for v in violations if v.get("severity") == "error"]
        if hard:
            try:
                from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

                handle_entity_created(
                    org_id=org_id,
                    payload={
                        "entity_type": "expense_policy_exception",
                        "entity_id": claim_id,
                        "started_by": actor_id,
                        "metadata": {"claim_id": claim_id, "violations": violations},
                    },
                )
            except Exception:
                raise ValueError(f"Policy violations: {hard[0].get('message')}") from None
        updated = claim_repository.set_status(org_id, claim_id=claim_id, status="submitted")
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "expense_claim",
                    "entity_id": claim_id,
                    "amount": float(claim.get("total_amount") or 0),
                    "started_by": actor_id,
                    "metadata": workflow_metadata(float(claim.get("total_amount") or 0), claim_id=claim_id),
                },
            )
        except Exception:
            pass
        self._audit(org_id, action="expense.claim.submitted", claim_id=claim_id, actor_id=actor_id, details={})
        return updated

    def mark_workflow_approved(self, org_id: str, *, claim_id: str) -> dict:
        return claim_repository.set_status(org_id, claim_id=claim_id, status="under_review", workflow_approved=True)

    def approve(
        self,
        org_id: str,
        *,
        claim_id: str,
        approver_id: str,
        skip_workflow_check: bool = False,
        auto_post: bool = True,
        auto_reimburse: bool = False,
    ) -> dict:
        claim = claim_repository.get(org_id, claim_id=claim_id)
        if not claim:
            raise ValueError("Claim not found")
        ensure_approvable(str(claim.get("status")))
        if not skip_workflow_check and not claim.get("workflow_approved"):
            raise ValueError("Expense claim workflow approval required")
        from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker

        try:
            enforce_maker_checker(created_by=str(claim.get("created_by") or ""), actor_user_id=approver_id, org_id=org_id)
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc

        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        posting_date = str(claim.get("claim_date") or "")[:10]
        if posting_date:
            ensure_posting_allowed(org_id, posting_date)

        items = claim_repository.list_items(org_id, claim_id=claim_id)
        payable_id = resolve_employee_payable_account(org_id)
        if not payable_id:
            raise ValueError("Employee reimbursement payable account not configured")
        total = float(claim.get("total_amount") or 0)
        lines = []
        for item in items:
            expense_id = item.get("expense_account_id") or resolve_expense_account(org_id)
            if not expense_id:
                raise ValueError("Expense account required for claim items")
            amt = float(item.get("amount") or 0) + float(item.get("gst_amount") or 0)
            lines.append({
                "account_id": expense_id,
                "debit_amount": amt,
                "credit_amount": 0,
                "line_description": str(item.get("expense_type") or "expense"),
            })
        lines.append({
            "account_id": payable_id,
            "debit_amount": 0,
            "credit_amount": total,
            "line_description": "Employee reimbursement payable",
        })

        journal = None
        post_result = None
        jid = None
        updated = None

        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            journal = create_draft_with_conn(
                conn,
                org_id,
                created_by=approver_id,
                journal_type="accrual",
                posting_date=posting_date or datetime.now(timezone.utc).date().isoformat(),
                description=f"Expense claim {claim.get('claim_number')}",
                source_type="expense_claim",
                source_id=claim_id,
                company_id=claim.get("company_id"),
                lines=lines,
                idempotency_key=f"expense-claim:{claim_id}",
            )
            jid = str(journal["journal"]["id"])
            approve_with_conn(conn, org_id, journal_id=jid, approver_id=approver_id, skip_maker_checker=True)
            if auto_post:
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=jid, posted_by=approver_id, defer_side_effects=True
                )

            from app.modules.erp.expenses.services.advance_service import advance_service

            advance_service.settle_against_claim_conn(
                conn, org_id, employee_id=str(claim["employee_id"]), claim_amount=total
            )

            updated = claim_repository.set_status_conn(
                conn,
                org_id,
                claim_id=claim_id,
                status="approved",
                approved_by=approver_id,
                workflow_approved=True,
                journal_id=jid,
            )

        if auto_post and journal:
            posting_orchestrator._emit_post_side_effects(
                org_id,
                journal_id=jid,
                journal=journal["journal"],
                batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                posted_by=approver_id,
            )

        emit_claim_approved(org_id, claim_id=claim_id, claim_number=str(claim.get("claim_number")))
        self._audit(org_id, action="expense.claim.approved", claim_id=claim_id, actor_id=approver_id, details={"journal_id": jid})

        if auto_reimburse:
            from app.modules.erp.expenses.services.reimbursement_service import reimbursement_service

            reimbursement_service.schedule(org_id, claim_id=claim_id, actor_id=approver_id)
        return updated

    def reject(self, org_id: str, *, claim_id: str, actor_id: str, reason: str) -> dict:
        claim = claim_repository.get(org_id, claim_id=claim_id)
        if not claim:
            raise ValueError("Claim not found")
        updated = claim_repository.set_status(org_id, claim_id=claim_id, status="rejected")
        emit_claim_rejected(org_id, claim_id=claim_id, reason=reason)
        return updated

    def cancel(self, org_id: str, *, claim_id: str, actor_id: str) -> dict:
        claim = claim_repository.get(org_id, claim_id=claim_id)
        if not claim:
            raise ValueError("Claim not found")
        ensure_cancellable(str(claim.get("status")))
        return claim_repository.set_status(org_id, claim_id=claim_id, status="cancelled")


claim_service = ClaimService()
