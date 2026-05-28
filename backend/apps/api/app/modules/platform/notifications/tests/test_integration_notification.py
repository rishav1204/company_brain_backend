from unittest.mock import MagicMock, patch

from app.modules.platform.notifications.services.notification_service import notification_service


@patch("app.modules.platform.notifications.services.notification_service.notification_repository")
@patch("app.modules.platform.notifications.services.notification_service.realtime_notification_service")
def test_in_app_dispatch_without_schema(mock_rt: MagicMock, mock_repo: MagicMock) -> None:
    mock_repo.schema_ready.return_value = False
    notification_service.dispatch(
        "org-1",
        notification_type="risk_alert",
        channel="in_app",
        priority="high",
        variables={"body": "test"},
    )
    mock_rt.push_toast.assert_called_once()
