from app.modules.workflows.services.retry_service import retry_delay_seconds, should_retry


def test_exponential_backoff() -> None:
    assert retry_delay_seconds(0) == 30
    assert retry_delay_seconds(1) == 60
    assert retry_delay_seconds(2) == 120


def test_max_retries() -> None:
    assert should_retry(4)
    assert not should_retry(5)
