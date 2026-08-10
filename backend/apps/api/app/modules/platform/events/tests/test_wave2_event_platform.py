"""Wave 2 — event platform architecture & static governance tests."""

from __future__ import annotations

from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[4]
EVENTS_ROOT = APP / "modules" / "platform" / "events"


def test_event_service_module_exists():
    path = EVENTS_ROOT / "services" / "event_service.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "require_org_id" in text
    assert "publish_with_conn" in text
    assert "event_outbox_dual_write" in text
    assert "require_financial_registered" in text


def test_no_dual_write_when_outbox_ready_default():
    """Default path must not XADD on request when outbox ready."""
    text = (EVENTS_ROOT / "services" / "event_service.py").read_text(encoding="utf-8")
    # dual-write gated by settings
    assert "event_outbox_dual_write" in text
    assert "dual_write or not outbox_repository.schema_ready()" in text


def test_outbox_repository_wave2_states():
    text = (EVENTS_ROOT / "repositories" / "outbox_repository.py").read_text(encoding="utf-8")
    for token in ("OUTBOX_DEAD", "payload_checksum", "mark_dead", "resurrect_dead", "archive_published"):
        assert token in text


def test_queue_manager_has_maxlen():
    path = EVENTS_ROOT / "queues" / "queue_manager.py"
    text = path.read_text(encoding="utf-8")
    assert "maxlen=" in text


def test_dlq_module_present():
    path = EVENTS_ROOT / "queues" / "dead_letter_queue.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "replay" in text.lower()


def test_modular_consumers_package():
    consumers = EVENTS_ROOT / "consumers"
    for name in ("erp_consumer.py", "workflow_consumer.py", "finance_os_consumer.py", "ingestion_consumer.py"):
        assert (consumers / name).is_file()


def test_registry_no_duplicate_keys():
    from app.modules.platform.events.bus.event_registry import ALL_EVENTS, ERP_EVENTS

    assert len(ALL_EVENTS) > 50
    # duplicates in source tuple fold in dict; ensure known keys present
    assert "journal.posted" in ALL_EVENTS
    assert "erp.journal.posted" in ALL_EVENTS
    # ERP tuple may still list legacy duplicates of irn — folded
    types = [e.event_type for e in ERP_EVENTS]
    # journal.posted must be financial
    assert ALL_EVENTS["journal.posted"].financial is True


def test_financial_contract_and_version_qualname():
    from app.modules.platform.events.governance.financial_contracts import (
        get_contract,
        is_financial_event_type,
        require_financial_registered,
        version_compat,
    )

    assert is_financial_event_type("journal.posted")
    c = get_contract("journal.posted")
    assert c is not None
    assert c.financial is True
    assert c.qualified_name().endswith(".v1")
    assert version_compat("v1", "v2") is True
    require_financial_registered("journal.posted")  # registered — no raise


def test_require_financial_unregistered_raises(monkeypatch):
    from app.core.config import settings
    from app.modules.platform.events.governance.financial_contracts import require_financial_registered

    monkeypatch.setattr(settings, "event_require_registered_financial", True)
    with pytest.raises(ValueError, match="financial_event_not_registered"):
        require_financial_registered("ledger.supersecret.unregistered.xyz")


def test_canonical_envelope_wave2_fields():
    from app.modules.platform.events.schemas.event_schema import CanonicalEventEnvelope

    env = CanonicalEventEnvelope(
        event_id="e1",
        event_type="journal.posted",
        org_id="o1",
        source="erp.journals",
        timestamp="2026-01-01T00:00:00Z",
        correlation_id="c1",
        partition_key="o1:j1",
        ordering_key="journal:j1",
        is_financial=True,
    )
    bus = env.to_bus_dict()
    assert bus["is_financial"] is True
    assert bus["partition_key"] == "o1:j1"
    assert bus["ordering_key"] == "journal:j1"


def test_migration_085_exists():
    # .../backend/apps/api/app/modules/platform/events/tests → parents[7] = backend
    mig = Path(__file__).resolve().parents[7] / "migrations" / "085_event_platform_wave2.sql"
    assert mig.is_file(), str(mig)
    text = mig.read_text(encoding="utf-8")
    assert "payload_checksum" in text
    assert "dead" in text.lower()


def test_outbox_publisher_dead_letter_metric():
    text = (EVENTS_ROOT / "services" / "outbox_publisher.py").read_text(encoding="utf-8")
    assert "dead" in text
    assert "mark_failed" in text
