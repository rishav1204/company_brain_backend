from __future__ import annotations

from app.modules.platform.events.bus.event_registry import ALL_EVENTS


def test_report_events_registered() -> None:
    for evt in (
        "report.generated",
        "report.exported",
        "report.snapshot.created",
        "reports.generate.requested",
        "reports.generate.completed",
        "reports.refresh.requested",
        "scheduler.reports.daily",
    ):
        assert evt in ALL_EVENTS


def test_reporting_router_prefix_constant() -> None:
    from pathlib import Path

    router_path = Path(__file__).resolve().parents[1] / "routes" / "router.py"
    text = router_path.read_text(encoding="utf-8")
    assert 'prefix="/erp/reports"' in text or "prefix='/erp/reports'" in text


def test_main_wires_reporting_router() -> None:
    from pathlib import Path

    main_path = Path(__file__).resolve().parents[4] / "main.py"
    text = main_path.read_text(encoding="utf-8")
    assert "erp_reporting_router" in text
