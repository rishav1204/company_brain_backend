from __future__ import annotations

"""AR sales invoice extraction via Finance OS invoice pipeline with sales-specific validation."""


def process_sales_document(org_id: str, *, document_id: str, customer_id: str | None = None) -> dict:
    from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository
    from app.modules.erp.ports.intelligence_registry import intelligence_registry

    result = intelligence_registry.invoice().run_pipeline(org_id, document_id=document_id, invoice_type="sales")
    if customer_id:
        customer = customer_repository.get(org_id, customer_id=customer_id)
        if not customer:
            raise ValueError("Customer not found for AR AI extraction")
        result["customer_id"] = customer_id
    result["invoice_type"] = "sales"
    result["module"] = "accounts_receivable"
    return result
