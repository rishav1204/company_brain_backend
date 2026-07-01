from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.platform.billing.exceptions import QuotaExceeded
from app.services.cache import api_quota_cache


@patch("app.services.cache.api_quota_cache.usage_service")
@patch("app.services.cache.api_quota_cache.get_redis_client")
def test_check_and_increment_uses_redis_without_db(mock_redis_fn, mock_usage) -> None:
    client = MagicMock()
    client.exists.return_value = True
    client.get.side_effect = lambda key: b"5" if "flushed" not in key else b"5"
    client.incr.return_value = 6
    mock_redis_fn.return_value = client

    with patch.object(api_quota_cache, "_get_cached_limit", return_value=100):
        api_quota_cache.check_and_increment("org-1")

    client.incr.assert_called_once()
    mock_usage.check_quota.assert_not_called()


@patch("app.services.cache.api_quota_cache.usage_service")
@patch("app.services.cache.api_quota_cache.get_redis_client")
def test_check_and_increment_raises_when_over_limit(mock_redis_fn, mock_usage) -> None:
    client = MagicMock()
    client.exists.return_value = True
    client.get.return_value = b"100"
    client.incr.return_value = 101
    mock_redis_fn.return_value = client

    with patch.object(api_quota_cache, "_get_cached_limit", return_value=100):
        with pytest.raises(QuotaExceeded):
            api_quota_cache.check_and_increment("org-1")
    client.decr.assert_called_once()
    mock_usage.check_quota.assert_not_called()


@patch("app.services.cache.api_quota_cache.usage_service")
@patch("app.services.cache.api_quota_cache.get_redis_client")
def test_check_and_increment_db_fallback_when_redis_unavailable(mock_redis_fn, mock_usage) -> None:
    mock_redis_fn.return_value = None
    api_quota_cache.check_and_increment("org-1")
    mock_usage.check_quota.assert_called_once_with("org-1", "api_calls_monthly", increment=1)
