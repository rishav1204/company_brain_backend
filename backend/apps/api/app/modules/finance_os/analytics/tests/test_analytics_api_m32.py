from __future__ import annotations

from app.modules.platform.events.bus.event_registry import ALL_EVENTS


def test_analytics_events_registered() -> None:
    for evt in (
        "kpi.updated",
        "insight.generated",
        "risk.detected",
        "dashboard.refreshed",
        "analytics.refresh.requested",
        "scheduler.analytics.daily",
    ):
        assert evt in ALL_EVENTS


def test_analytics_router_prefix_constant() -> None:
    from pathlib import Path

    router_path = Path(__file__).resolve().parents[1] / "routes" / "router.py"
    text = router_path.read_text(encoding="utf-8")
    assert 'prefix="/finance-os/analytics"' in text
