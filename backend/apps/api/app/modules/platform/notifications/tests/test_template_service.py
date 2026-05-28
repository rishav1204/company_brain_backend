from app.modules.platform.notifications.services.template_service import mask_sensitive_value


def test_mask_sensitive_pan() -> None:
    assert mask_sensitive_value("pan", "ABCDE1234F") == "XXXXXX234F"


def test_mask_non_sensitive() -> None:
    assert mask_sensitive_value("amount", "500000") == "500000"
