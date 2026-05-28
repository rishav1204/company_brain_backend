from app.modules.core.iam.services.password_service import hash_password, verify_password


def test_argon2_hash_and_verify() -> None:
    hashed = hash_password("Str0ngPassword!1")
    assert hashed.startswith("$argon2")
    assert verify_password("Str0ngPassword!1", hashed)
    assert not verify_password("wrong", hashed)
