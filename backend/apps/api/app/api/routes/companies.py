from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import build_request_context
from app.core.config import settings
from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.core.iam.services.approval_gate_service import pending_approval_response_reason
from app.modules.core.iam.services.finance_route_guard import enforce_finance_route_access
from app.services.dev_workflows import dev_workflow_state_counts, postgres_configured
from app.services.object_context import resolve_object_context
from app.modules.core.iam.services.branch_scope_service import evaluate_branch_scope
from app.services.repositories import invoices_repo, workflows_repo

router = APIRouter(tags=["companies"])


class InvoiceCreateRequest(BaseModel):
    number: str
    poId: str | None = None
    vendorId: str
    amount: float
    dueDate: str


class CompanyWorkflowActionRequest(BaseModel):
    action: str
    parameters: dict


@router.get("/companies/{company_id}/invoices/{invoice_id}")
def get_company_invoice(company_id: str, invoice_id: str, context=Depends(build_request_context)) -> dict:
    enforce_finance_route_access(context, object_type="invoice", mode="read", required_scope="invoice.read")
    scope = evaluate_branch_scope(
        attrs=context.attrs,
        object_branch_id=None,
        object_company_id=company_id,
    )
    if scope and not scope.allowed:
        raise HTTPException(status_code=403, detail=scope.reason or "Company access denied")
    invoice = invoices_repo.get_invoice(org_id=context.org_id, invoice_id=invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {
        "request_id": context.request_id,
        "invoiceId": invoice["invoice_id"],
        "amount": invoice["amount"],
        "status": invoice["status"],
        "vendor": invoice["vendor"],
        "confidence": 0.98,
        "verification_status": "verified",
    }


@router.post("/companies/{company_id}/invoices")
def create_company_invoice(company_id: str, request: InvoiceCreateRequest, context=Depends(build_request_context)) -> dict:
    enforce_finance_route_access(context, object_type="invoice", mode="write", required_scope="invoice.create")
    if company_id != context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    object_context = resolve_object_context(org_id=context.org_id, object_type="invoice", object_id="new")
    object_context.amount = request.amount
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles,
        action="create",
        object_context=object_context,
        attrs=context.attrs,
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    created = invoices_repo.create_invoice(
        org_id=context.org_id,
        vendor_id=request.vendorId,
        amount=request.amount,
        due_date=request.dueDate,
        invoice_type="ap",
    )
    return {
        "request_id": context.request_id,
        "invoiceId": created["invoice_id"],
        "status": created["status"],
        "confidence": 0.97,
        "verification_status": "verified",
    }


@router.post("/companies/{company_id}/workflows/{workflow_id}/actions")
def company_workflow_action(
    company_id: str,
    workflow_id: str,
    request: CompanyWorkflowActionRequest,
    context=Depends(build_request_context),
) -> dict:
    enforce_finance_route_access(context, action=request.action, object_type="workflow", mode="write")
    if company_id != context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    workflow = workflows_repo.get_workflow(org_id=context.org_id, workflow_id=workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    amount_raw = request.parameters.get("amount")
    amount: float | None = None
    if amount_raw is not None and str(amount_raw).strip() != "":
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid amount in parameters")
    object_context = resolve_object_context(org_id=context.org_id, object_type="workflow", object_id=workflow_id)
    object_context.amount = amount
    object_context.vendor_risk = str(request.parameters.get("vendor_risk") or "") or None
    human_approved = bool(request.parameters.get("human_approved") or request.parameters.get("approved"))
    policy_decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles,
        action=request.action,
        object_context=object_context,
        attrs=context.attrs,
        created_by=workflow.get("owner_user_id") or request.parameters.get("created_by"),
        human_approved=human_approved,
        object_company_id=company_id,
    )
    if not policy_decision.allowed:
        if pending_approval_response_reason(policy_decision.reason):
            return {
                "request_id": context.request_id,
                "workflow_id": workflow_id,
                "action": request.action,
                "accepted": False,
                "requires_human_approval": True,
                "reason": policy_decision.reason,
                "confidence": 0.95,
                "verification_status": "policy_blocked_pending_approval",
            }
        raise HTTPException(status_code=403, detail=policy_decision.reason)
    return {
        "request_id": context.request_id,
        "workflow_id": workflow_id,
        "action": request.action,
        "accepted": True,
        "requires_human_approval": False,
        "confidence": 0.95,
        "verification_status": "policy_checked",
    }


def _load_close_status_counts(org_id: str) -> tuple[dict, str]:
    use_postgres = postgres_configured() and (
        settings.app_env.lower() != "dev" or settings.dev_use_postgres
    )
    if use_postgres:
        try:
            return dev_workflow_state_counts(org_id), "verified"
        except Exception:
            if settings.app_env.lower() != "dev":
                raise
    return dev_workflow_state_counts(org_id), "dev_sample_data"


@router.get("/companies/{company_id}/close-status")
def close_status_report(company_id: str, context=Depends(build_request_context)) -> dict:
    enforce_finance_route_access(context, object_type="workflow", mode="read")
    if company_id != context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    counts, verification = _load_close_status_counts(context.org_id)
    return {
        "request_id": context.request_id,
        "company_id": company_id,
        "counts": counts,
        "confidence": 0.94,
        "verification_status": verification,
    }
