from app.modules.platform.notifications.services.retry_service import notification_retry_delay, should_retry_notification


def test_exponential_backoff() -> None:
    assert notification_retry_delay(0) == 5
    assert notification_retry_delay(1) == 10
    assert notification_retry_delay(2) == 20


def test_should_retry_respects_max() -> None:
    assert should_retry_notification(1) is True
    assert should_retry_notification(10) is False
