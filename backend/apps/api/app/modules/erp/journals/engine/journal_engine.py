from __future__ import annotations

from app.modules.erp.journals.services.journal_service import journal_service


class JournalEngine:
    """Orchestration facade for journal draft lifecycle."""

    create_draft = journal_service.create_draft
    get = journal_service.get
    list = journal_service.list
    update_draft = journal_service.update_draft
    cancel = journal_service.cancel


journal_engine = JournalEngine()
