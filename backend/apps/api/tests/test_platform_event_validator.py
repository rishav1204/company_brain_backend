import pytest

from app.modules.platform.events.validators.event_validator import validate_event_envelope


def test_valid_envelope() -> None:
    validate_event_envelope(
        {"event_id": "1", "event_type": "invoice.created", "org_id": "o1", "source": "erp.ap"}
    )


def test_invalid_envelope_missing_field() -> None:
    with pytest.raises(ValueError):
        validate_event_envelope({"event_type": "invoice.created"})
