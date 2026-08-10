from __future__ import annotations

from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.ports.intelligence_registry import intelligence_registry


class AiCollectionService:
    def forecast(self, org_id: str) -> dict:
        invoices = ar_invoice_repository.list_outstanding(org_id)
        return intelligence_registry.ar_collections().forecast_collections(invoices)

    def assistant(self, org_id: str, *, limit: int = 10) -> dict:
        invoices = ar_invoice_repository.list_outstanding(org_id)
        return intelligence_registry.ar_collections().recommend_collections(invoices, limit=limit)


ai_collection_service = AiCollectionService()
