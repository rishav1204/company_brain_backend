"""Platform events module tests."""
from __future__ import annotations

from pathlib import Path

APP = Path(__file__).resolve().parents[4]


def test_event_service_module_exists():
    path = APP / "modules" / "platform" / "events" / "services" / "event_service.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "require_org_id" in text


def test_queue_manager_has_maxlen():
    path = APP / "modules" / "platform" / "events" / "queues" / "queue_manager.py"
    text = path.read_text(encoding="utf-8")
    assert "maxlen=" in text


def test_modular_consumers_package():
    consumers = APP / "modules" / "platform" / "events" / "consumers"
    for name in ("erp_consumer.py", "workflow_consumer.py", "finance_os_consumer.py", "ingestion_consumer.py"):
        assert (consumers / name).is_file()
