from app.modules.core.iam.services.password_service import hash_password, verify_password


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("test-password-123!")
    assert verify_password("test-password-123!", hashed)
    assert not verify_password("wrong", hashed)
