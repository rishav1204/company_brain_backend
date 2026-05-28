from app.modules.core.iam.services.api_key_auth_service import scope_allows


def test_scope_allows_exact_and_wildcard() -> None:
    assert scope_allows(["user.read"], "user.read")
    assert scope_allows(["*"], "payment.approve")
    assert not scope_allows(["user.read"], "user.manage")
