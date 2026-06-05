from app.modules.erp.journals.validators.journal_validator import journal_validator


def test_posted_status_not_editable() -> None:
    try:
        journal_validator.ensure_editable("posted")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_draft_is_editable() -> None:
    journal_validator.ensure_editable("draft")
