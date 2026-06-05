def test_event_registry_has_gl_events() -> None:
    from app.modules.platform.events.bus.event_registry import get_event_definition

    assert get_event_definition("erp.ledger.posted") is not None
    assert get_event_definition("erp.ledger.reversed") is not None
    assert get_event_definition("erp.fiscal_period.closed") is not None
    assert get_event_definition("erp.trial_balance.generated") is not None


def test_event_registry_has_journal_events() -> None:
    from app.modules.platform.events.bus.event_registry import get_event_definition

    assert get_event_definition("journal.created") is not None
    assert get_event_definition("journal.approved") is not None
    assert get_event_definition("journal.posted") is not None
    assert get_event_definition("journal.reversed") is not None


def test_journal_module_importable() -> None:
    from app.modules.erp.journals.services.journal_service import journal_service  # noqa: F401
    from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator  # noqa: F401
    from app.modules.erp.journals.validators.journal_validator import journal_validator  # noqa: F401

