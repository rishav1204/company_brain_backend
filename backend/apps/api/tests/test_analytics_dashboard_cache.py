from __future__ import annotations

from unittest.mock import patch

from app.modules.finance_os.analytics.services.executive_dashboard_service import executive_dashboard_service
from app.services.cache.redis_cache import get_cached, invalidate_namespace, set_cached


@patch("app.modules.finance_os.analytics.services.executive_dashboard_service.analytics_schema_repository.schema_ready", return_value=True)
@patch("app.modules.finance_os.analytics.services.executive_dashboard_service.dashboard_snapshot_repository.get_latest", return_value=None)
@patch.object(executive_dashboard_service, "_build_live")
def test_dashboard_cache_hit_skips_build(mock_build, _snap, _schema) -> None:
    payload = {"snapshot_date": "2026-06-30", "widgets": {}}
    set_cached("org-1", "analytics.dashboard", payload, {"snapshot_date": "2026-06-30"})

    result = executive_dashboard_service.get("org-1", snapshot_date="2026-06-30")

    assert result == payload
    mock_build.assert_not_called()


@patch("app.modules.finance_os.analytics.services.executive_dashboard_service.analytics_schema_repository.schema_ready", return_value=True)
@patch("app.modules.finance_os.analytics.services.executive_dashboard_service.dashboard_snapshot_repository.get_latest", return_value=None)
@patch.object(executive_dashboard_service, "_build_live")
def test_dashboard_cache_miss_builds_and_sets(mock_build, _snap, _schema) -> None:
    invalidate_namespace("org-1", "analytics")
    built = {"snapshot_date": "2026-06-30", "widgets": {"cash_position": None}}
    mock_build.return_value = built

    result = executive_dashboard_service.get("org-1", snapshot_date="2026-06-30")

    assert result == built
    mock_build.assert_called_once()
    cached = get_cached("org-1", "analytics.dashboard", {"snapshot_date": "2026-06-30"})
    assert cached == built


@patch("app.modules.finance_os.analytics.services.executive_dashboard_service.dashboard_snapshot_repository.upsert")
@patch.object(executive_dashboard_service, "_build_live", return_value={"snapshot_date": "2026-06-30"})
def test_build_and_cache_invalidates_namespace(mock_build, mock_upsert) -> None:
    set_cached("org-1", "analytics.dashboard", {"stale": True}, {"snapshot_date": "2026-06-30"})

    executive_dashboard_service.build_and_cache("org-1", snapshot_date="2026-06-30")

    mock_upsert.assert_called_once()
    assert get_cached("org-1", "analytics.dashboard", {"snapshot_date": "2026-06-30"}) is None
