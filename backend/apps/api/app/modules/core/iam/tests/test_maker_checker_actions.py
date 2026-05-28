from app.modules.core.iam.services.maker_checker_service import requires_maker_checker


def test_requires_maker_checker_covers_approve_and_post() -> None:
    assert requires_maker_checker("approve_payment")
    assert requires_maker_checker("post_journal")
    assert requires_maker_checker("payment.approve")
    assert not requires_maker_checker("read")
