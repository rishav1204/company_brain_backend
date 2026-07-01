from unittest.mock import MagicMock, patch

from app.modules.platform.governance.repositories.policy_repository import policy_repository


@patch("app.modules.platform.governance.repositories.policy_repository.get_db_conn")
@patch.object(policy_repository, "schema_ready", return_value=True)
def test_list_active_includes_limit_param(_ready, mock_get_db) -> None:
    conn = MagicMock()
    cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = []

    policy_repository.list_active("org-1", limit=10)

    args = cursor.execute.call_args[0]
    assert args[1] == ("org-1", 10)
