from __future__ import annotations

from app.modules.erp.journals.services.accrual_service import accrual_service


class AccrualEngine:
    create_accrual = accrual_service.create_accrual
    list_accruals = accrual_service.list_accruals
    process_due_reversals = accrual_service.process_due_reversals


accrual_engine = AccrualEngine()
