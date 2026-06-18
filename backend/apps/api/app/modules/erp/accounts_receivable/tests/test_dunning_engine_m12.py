from app.modules.erp.accounts_receivable.engine.dunning_engine import determine_dunning_action


def test_pre_due_reminder() -> None:
    action = determine_dunning_action(aging_days=-10)
    assert action and action["stage"] == "pre_due_reminder"


def test_legal_review_overdue() -> None:
    action = determine_dunning_action(aging_days=120)
    assert action and action["stage"] == "overdue_90"
