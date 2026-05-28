from unittest.mock import MagicMock, patch

from app.modules.platform.events.queues.queue_manager import QueueManager


def _envelope(attempts: int = 0, force_fail: bool = False) -> dict:
    return {
        "event_id": "evt-1",
        "event_type": "test.event",
        "org_id": "org-1",
        "payload": {"force_fail": force_fail},
        "_attempts": attempts,
    }


def test_fail_claim_retries_before_dlq() -> None:
    mgr = QueueManager()
    mgr.client = MagicMock()
    mgr.use_streams = False
    published: list[dict] = []

    def capture_publish(envelope, **kwargs):
        published.append(envelope)
        from app.modules.platform.events.queues.queue_manager import QueuePublishResult

        return QueuePublishResult(status="queued", queue="workflow.execution", envelope=envelope)

    mgr.publish = capture_publish  # type: ignore[method-assign]

    with patch("app.modules.platform.events.queues.queue_manager.settings") as mock_settings:
        mock_settings.event_retry_max_attempts = 3
        result = mgr.fail_claim("workflow.execution", _envelope(attempts=0), "token-1", "boom")

    assert result.status == "retry"
    assert published
    assert published[0]["_attempts"] == 1


def test_fail_claim_moves_to_dlq_after_max_attempts() -> None:
    mgr = QueueManager()
    mgr.client = MagicMock()
    mgr.use_streams = False
    mgr._move_to_dlq = MagicMock()  # type: ignore[method-assign]
    mgr._emit_system_failure = MagicMock()  # type: ignore[method-assign]

    with (
        patch("app.modules.platform.events.queues.queue_manager.settings") as mock_settings,
        patch("app.modules.platform.events.services.retry_service.settings") as retry_settings,
    ):
        mock_settings.event_retry_max_attempts = 2
        retry_settings.event_retry_max_attempts = 2
        # After schedule_retry, attempts become 2; should_retry(2) with max 2 → DLQ
        result = mgr.fail_claim("workflow.execution", _envelope(attempts=1), "token-1", "boom")

    assert result.status == "dlq"
    mgr._move_to_dlq.assert_called_once()
    mgr._emit_system_failure.assert_called_once()
