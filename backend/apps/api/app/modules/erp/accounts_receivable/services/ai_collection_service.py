from __future__ import annotations

from app.modules.erp.accounts_receivable.ai.collection_assistant import recommend_collections
from app.modules.erp.accounts_receivable.ai.collection_predictor import forecast_collections
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository


class AiCollectionService:
    def forecast(self, org_id: str) -> dict:
        invoices = ar_invoice_repository.list_outstanding(org_id)
        return forecast_collections(invoices)

    def assistant(self, org_id: str, *, limit: int = 10) -> dict:
        invoices = ar_invoice_repository.list_outstanding(org_id)
        return recommend_collections(invoices, limit=limit)


ai_collection_service = AiCollectionService()
