from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.modules.platform.events.bus.event_registry import get_event_definition

ORG = "00000000-0000-0000-0000-000000000001"
HOLD = "10000000-0000-0000-0000-000000000001"
SUB_A = "20000000-0000-0000-0000-000000000001"
SUB_B = "30000000-0000-0000-0000-000000000001"


def test_migration_060_exists() -> None:
    mig = Path(__file__).resolve().parents[7] / "migrations" / "060_multi_entity_consolidation.sql"
    assert mig.exists()
    text = mig.read_text(encoding="utf-8")
    assert "erp.consolidation_runs" in text
    assert "erp.intercompany_transactions" in text
    assert "consolidated_trial_balance_mv" in text


def test_bootstrap_script_exists() -> None:
    script = Path(__file__).resolve().parents[7] / "scripts" / "bootstrap_consolidation_hierarchy.py"
    assert script.exists()


def test_router_prefix() -> None:
    text = Path(__file__).resolve().parents[1].joinpath("routes", "router.py").read_text(encoding="utf-8")
    assert 'prefix="/erp/consolidation"' in text


def test_entity_routes_hierarchy() -> None:
    text = Path(__file__).resolve().parents[1].joinpath("routes", "entity_routes.py").read_text(encoding="utf-8")
    assert "/entities/hierarchy" in text


def test_intercompany_routes() -> None:
    text = Path(__file__).resolve().parents[1].joinpath("routes", "intercompany_routes.py").read_text(encoding="utf-8")
    assert "/intercompany" in text
    assert "mismatch" in text


def test_consolidation_run_route() -> None:
    text = Path(__file__).resolve().parents[1].joinpath("routes", "consolidation_routes.py").read_text(encoding="utf-8")
    assert "/consolidation/run" in text
    assert "consolidation.run" in text


def test_branch_pnl_route() -> None:
    text = Path(__file__).resolve().parents[1].joinpath("routes", "branch_routes.py").read_text(encoding="utf-8")
    assert "branch" in text
    assert "pnl" in text


def test_event_definition_consolidation_completed() -> None:
    defn = get_event_definition("consolidation.completed")
    assert defn is not None
    assert defn.event_type == "consolidation.completed"


def test_event_definition_intercompany_created() -> None:
    defn = get_event_definition("intercompany.created")
    assert defn is not None


@patch("app.modules.erp.consolidation.routes.consolidation_routes.require_consolidation_run")
@patch("app.modules.erp.consolidation.routes.consolidation_routes.consolidation_service")
def test_run_consolidation_route_handler(mock_svc: MagicMock, _mock_guard: MagicMock) -> None:
    from app.modules.erp.consolidation.routes.consolidation_routes import ConsolidationRunRequest, run_consolidation
    from app.modules.erp.consolidation.engine.consolidation_engine import ConsolidationResult

    mock_svc.run.return_value = ConsolidationResult(run_id="run-1", status="completed", consolidated_rows=10)
    ctx = MagicMock(org_id=ORG, user_id="u1", roles=["cfo"], request_id="req-1", attrs={})
    out = run_consolidation(
        ConsolidationRunRequest(group_company_id=HOLD, fiscal_period_id="p1", dry_run=True),
        ctx,
    )
    assert out["status"] == "completed"


@patch("app.modules.erp.consolidation.routes.intercompany_routes.require_intercompany_write")
@patch("app.modules.erp.consolidation.routes.intercompany_routes.intercompany_service")
def test_create_intercompany_route(mock_svc: MagicMock, _mock_guard: MagicMock) -> None:
    from app.modules.erp.consolidation.routes.intercompany_routes import IntercompanyCreateRequest, create_intercompany

    mock_svc.register.return_value = {"id": "ic-1", "amount": 1000}
    ctx = MagicMock(org_id=ORG, user_id="u1", roles=["cfo"], request_id="req-1", attrs={})
    out = create_intercompany(
        IntercompanyCreateRequest(
            source_company_id=SUB_A,
            target_company_id=SUB_B,
            transaction_type="intercompany_loan",
            amount=1000,
        ),
        ctx,
    )
    assert out["item"]["id"] == "ic-1"


def test_m35_doc_exists() -> None:
    doc = Path(__file__).resolve().parents[7] / "ERP_MODULES" / "M35_consolidation.md"
    assert doc.exists()
    assert "Golden rule" in doc.read_text(encoding="utf-8")


def test_erp_master_map_m35() -> None:
    text = Path(__file__).resolve().parents[7].joinpath("ERP_MASTER_MODULE_MAP.md").read_text(encoding="utf-8")
    assert "M35" in text
    assert "Done" in text
