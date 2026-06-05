from __future__ import annotations

from app.modules.erp.journals.services.recurring_journal_service import recurring_journal_service


class RecurringEngine:
    create_template = recurring_journal_service.create_template
    list_templates = recurring_journal_service.list_templates
    deactivate = recurring_journal_service.deactivate
    run_due = recurring_journal_service.run_due


recurring_engine = RecurringEngine()
