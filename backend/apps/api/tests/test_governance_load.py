from app.modules.platform.governance.services.audit_service import audit_service, mask_sensitive_fields


def test_mask_many_fields_performance() -> None:
    payload = {f"field_{i}": f"value_{i}" for i in range(500)}
    payload["pan"] = "ABCDE1234F"
    masked = mask_sensitive_fields(payload)
    assert masked["pan"].startswith("enc:")
    assert len(masked) == 501


def test_hash_prompt_batch() -> None:
    hashes = [audit_service.hash_prompt(f"prompt-{i}") for i in range(200)]
    assert len(set(hashes)) == 200
