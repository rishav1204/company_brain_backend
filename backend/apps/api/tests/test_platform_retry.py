from app.modules.platform.events.services.retry_service import retry_delay_seconds, should_retry


def test_exponential_backoff() -> None:
    assert retry_delay_seconds(0) == 5
    assert retry_delay_seconds(1) == 10
    assert retry_delay_seconds(2) == 20


def test_should_retry_respects_max() -> None:
    assert should_retry(4, 5) is True
    assert should_retry(5, 5) is False
