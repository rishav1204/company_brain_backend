from __future__ import annotations

from app.modules.erp.journals.services.approval_service import approval_service


class ApprovalEngine:
    submit_for_approval = approval_service.submit_for_approval
    approve = approval_service.approve
    reject = approval_service.reject
    list_approval_queue = approval_service.list_approval_queue


approval_engine = ApprovalEngine()
