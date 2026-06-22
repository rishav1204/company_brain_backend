from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import RequestContext, build_request_context


EXPENSE_ADMIN_ROLES = {
    "expense_manager", "finance_reviewer", "cfo", "controller", "finance_manager", "tenant_admin",
}
EXPENSE_READ_ROLES = EXPENSE_ADMIN_ROLES | {"employee", "manager", "auditor", "analyst"}


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def _check(context: RequestContext, *, read_only: bool = False, approve: bool = False, policy: bool = False) -> RequestContext:
    enforce_billing(context.org_id, "expense")
    roles = {r.lower() for r in (context.roles or [])}
    perms = {p.lower() for p in (context.permissions or [])}
    if "*" in perms or "expense.admin" in perms:
        return context
    if policy and ("expense.policy" in perms or roles & EXPENSE_ADMIN_ROLES):
        return context
    if approve and ("expense.approve" in perms or roles & EXPENSE_ADMIN_ROLES):
        return context
    if read_only and roles & EXPENSE_READ_ROLES:
        return context
    if not read_only and ("expense.create" in perms or roles & (EXPENSE_ADMIN_ROLES | {"employee"})):
        return context
    if read_only and any(p.startswith("expense.") for p in perms):
        return context
    if not read_only and any(p in perms for p in ("expense.create", "expense.reimburse")):
        return context
    raise HTTPException(status_code=403, detail="Expense access required")


def require_expense_read(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, read_only=True)


def require_expense_create(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context)


def require_expense_approve(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, approve=True)


def require_expense_reimburse(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    roles = {r.lower() for r in (context.roles or [])}
    perms = {p.lower() for p in (context.permissions or [])}
    if "*" in perms or "expense.reimburse" in perms or "expense.admin" in perms or roles & EXPENSE_ADMIN_ROLES:
        return context
    raise HTTPException(status_code=403, detail="Expense reimbursement access required")


def require_expense_policy(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    return _check(context, policy=True)
