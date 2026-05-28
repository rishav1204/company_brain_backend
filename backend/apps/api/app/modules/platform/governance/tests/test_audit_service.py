from app.modules.platform.governance.services.audit_service import audit_service, mask_sensitive_fields
from app.modules.platform.governance.validators.audit_validator import validate_audit_entry


def test_mask_sensitive_fields() -> None:
    masked = mask_sensitive_fields({"pan": "ABCDE1234F", "note": "ok"})
    assert masked["pan"].startswith("enc:")
    assert masked["note"] == "ok"


def test_validate_audit_entry_requires_fields() -> None:
    try:
        validate_audit_entry({"action": "", "object_ref": "x"})
        assert False
    except ValueError:
        pass


def test_hash_prompt_stable() -> None:
    h1 = audit_service.hash_prompt("test prompt")
    h2 = audit_service.hash_prompt("test prompt")
    assert h1 == h2
    assert len(h1) == 64
