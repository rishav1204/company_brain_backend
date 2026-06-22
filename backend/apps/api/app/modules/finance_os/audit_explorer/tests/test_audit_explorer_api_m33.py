from __future__ import annotations

from pathlib import Path

from app.modules.platform.events.bus.event_registry import ALL_EVENTS


def test_audit_events_registered() -> None:
    for evt in (
        "audit.timeline.updated",
        "audit.evidence.linked",
        "audit.ai_decision.recorded",
    ):
        assert evt in ALL_EVENTS


def test_audit_router_prefix_constant() -> None:
    router_path = Path(__file__).resolve().parents[1] / "routes" / "router.py"
    text = router_path.read_text(encoding="utf-8")
    assert 'prefix="/finance-os/audit"' in text


def test_timeline_route_module_exists() -> None:
    path = Path(__file__).resolve().parents[1] / "routes" / "timeline_routes.py"
    assert path.exists()
    assert "object_timeline" in path.read_text(encoding="utf-8")


def test_evidence_route_module_exists() -> None:
    path = Path(__file__).resolve().parents[1] / "routes" / "evidence_routes.py"
    assert "object_evidence" in path.read_text(encoding="utf-8")


def test_ai_audit_route_module_exists() -> None:
    path = Path(__file__).resolve().parents[1] / "routes" / "ai_audit_routes.py"
    assert "ai_decision_trail" in path.read_text(encoding="utf-8")


def test_workflow_audit_route_module_exists() -> None:
    path = Path(__file__).resolve().parents[1] / "routes" / "workflow_audit_routes.py"
    assert "approval_chain" in path.read_text(encoding="utf-8")


def test_copilot_route_module_exists() -> None:
    path = Path(__file__).resolve().parents[1] / "routes" / "copilot_routes.py"
    text = path.read_text(encoding="utf-8")
    assert "copilot_ask" in text
    assert "refresh_object" in text


def test_main_py_includes_audit_router() -> None:
    main_path = Path(__file__).resolve().parents[4] / "main.py"
    text = main_path.read_text(encoding="utf-8")
    assert "finance_os_audit_explorer_router" in text


def test_event_consumer_wires_m33() -> None:
    ec_path = Path(__file__).resolve().parents[4] / "services" / "event_consumers.py"
    text = ec_path.read_text(encoding="utf-8")
    assert "_consume_audit_explorer_materialize" in text


def test_langgraph_registers_audit_copilot() -> None:
    lg_path = Path(__file__).resolve().parents[4] / "services" / "langgraph_runner.py"
    text = lg_path.read_text(encoding="utf-8")
    assert "audit_copilot" in text


def test_migration_file_exists() -> None:
    mig = Path(__file__).resolve().parents[7] / "migrations" / "058_finance_audit_explorer.sql"
    assert mig.exists()
    text = mig.read_text(encoding="utf-8")
    assert "finance_audit.audit_timelines" in text
    assert "finance_audit.ai_decision_trails" in text


def test_bootstrap_script_exists() -> None:
    script = Path(__file__).resolve().parents[7] / "scripts" / "bootstrap_finance_audit.py"
    assert script.exists()


def test_m33_docs_exist() -> None:
    doc = Path(__file__).resolve().parents[7] / "ERP_MODULES" / "M33_audit_explorer.md"
    assert doc.exists()
    assert "Golden rule" in doc.read_text(encoding="utf-8")


def test_master_map_m33_done() -> None:
    doc = Path(__file__).resolve().parents[7] / "ERP_MASTER_MODULE_MAP.md"
    assert "M33 | Audit Explorer" in doc.read_text(encoding="utf-8")
    assert "| M33 | Audit Explorer | 7 | 2 | Done |" in doc.read_text(encoding="utf-8")
