from __future__ import annotations

from app.modules.platform.integrations.adapters.canonical_models import CanonicalInvoice, CanonicalJournal
from app.modules.platform.integrations.services.connector_registry import connector_registry


class TallyConnector:
    connector_type = "accounting"
    provider_name = "tally"

    def health(self) -> dict:
        return {"ready": True, "mode": "stub"}

    def export_journal(self, *, journal: dict) -> dict:
        return {"status": "queued", "provider": "tally", "journal_id": journal.get("id")}

    def export_invoice(self, *, invoice: dict) -> dict:
        return {"status": "queued", "provider": "tally", "invoice_id": invoice.get("id")}


class ZohoConnector:
    connector_type = "accounting"
    provider_name = "zoho"

    def health(self) -> dict:
        return {"ready": True, "mode": "stub"}

    def export_journal(self, *, journal: dict) -> dict:
        return {"status": "queued", "provider": "zoho", "journal_id": journal.get("id")}


class SapConnector:
    connector_type = "accounting"
    provider_name = "sap"

    def health(self) -> dict:
        return {"ready": True, "mode": "stub"}

    def export_journal(self, *, journal: CanonicalJournal | dict) -> dict:
        jid = journal.get("id") if isinstance(journal, dict) else getattr(journal, "id", None)
        return {"status": "queued", "provider": "sap", "journal_id": jid}


connector_registry.register(TallyConnector())
connector_registry.register(ZohoConnector())
connector_registry.register(SapConnector())
