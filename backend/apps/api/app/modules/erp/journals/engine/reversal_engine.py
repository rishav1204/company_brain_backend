from __future__ import annotations

from app.modules.erp.journals.services.reversal_service import journal_reversal_service


class ReversalEngine:
    reverse = journal_reversal_service.reverse


reversal_engine = ReversalEngine()
