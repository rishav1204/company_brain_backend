from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.erp.consolidation.engine import (
    currency_engine,
    elimination_engine,
    ownership_engine,
    reporting_engine,
)
from app.modules.erp.consolidation.engine.consolidation_engine import ConsolidationResult, run_consolidation
from app.modules.erp.consolidation.services.entity_service import _would_create_cycle, entity_service


ORG = "00000000-0000-0000-0000-000000000001"
HOLD = "10000000-0000-0000-0000-000000000001"
SUB_A = "20000000-0000-0000-0000-000000000001"
SUB_B = "30000000-0000-0000-0000-000000000001"


# --- ownership engine ---


def test_ownership_full_subsidiary() -> None:
    r = ownership_engine.compute_ownership_split(subsidiary_profit=1_000_000, ownership_percent=100)
    assert r["parent_share"] == 1_000_000
    assert r["minority_interest"] == 0


def test_ownership_eighty_percent() -> None:
    r = ownership_engine.compute_ownership_split(subsidiary_profit=1_000_000, ownership_percent=80)
    assert r["parent_share"] == 800_000
    assert r["minority_interest"] == 200_000


def test_ownership_fifty_one_percent() -> None:
    r = ownership_engine.compute_ownership_split(subsidiary_profit=100, ownership_percent=51)
    assert r["parent_share"] == 51
    assert r["minority_interest"] == 49


def test_ownership_caps_at_100() -> None:
    r = ownership_engine.compute_ownership_split(subsidiary_profit=100, ownership_percent=150)
    assert r["parent_share"] == 100


def test_ownership_zero_profit() -> None:
    r = ownership_engine.compute_ownership_split(subsidiary_profit=0, ownership_percent=80)
    assert r["minority_interest"] == 0


# --- currency engine ---


def test_currency_same_passes() -> None:
    assert currency_engine.validate_same_currency(["INR", "INR"]) is None


def test_currency_mixed_fails() -> None:
    err = currency_engine.validate_same_currency(["INR", "USD"])
    assert err is not None
    assert "USD" in err


def test_currency_translate_same() -> None:
    assert currency_engine.translate_amount(100, from_currency="INR", to_currency="INR") == 100


def test_currency_translate_with_rate() -> None:
    assert currency_engine.translate_amount(100, from_currency="USD", to_currency="INR", rate=83) == 8300


# --- elimination engine ---


def test_elimination_ic_balance() -> None:
    lines = elimination_engine.build_ic_eliminations(
        [{"source_company_id": SUB_A, "target_company_id": SUB_B, "amount": 500_000}]
    )
    assert len(lines) == 1
    assert lines[0]["elimination_type"] == "intercompany_balance"


def test_elimination_skips_zero_balance() -> None:
    assert elimination_engine.build_ic_eliminations([{"source_company_id": SUB_A, "target_company_id": SUB_B, "amount": 0}]) == []


def test_elimination_deduplicates_pairs() -> None:
    balances = [
        {"source_company_id": SUB_A, "target_company_id": SUB_B, "amount": 100},
        {"source_company_id": SUB_B, "target_company_id": SUB_A, "amount": 50},
    ]
    lines = elimination_engine.build_ic_eliminations(balances)
    assert len(lines) == 1


def test_elimination_matched_transactions() -> None:
    txs = [
        {
            "id": "tx1",
            "status": "matched",
            "amount": 100_000,
            "source_company_id": SUB_A,
            "target_company_id": SUB_B,
            "transaction_type": "intercompany_loan",
        }
    ]
    lines = elimination_engine.build_ic_transaction_eliminations(txs)
    assert len(lines) == 1
    assert lines[0]["debit_amount"] == lines[0]["credit_amount"]


def test_elimination_ignores_open_transactions() -> None:
    txs = [{"id": "tx1", "status": "open", "amount": 100_000}]
    assert elimination_engine.build_ic_transaction_eliminations(txs) == []


# --- reporting engine merge ---


def test_merge_trial_balances() -> None:
    a = [{"account_id": "acc1", "account_code": "1000", "account_name": "Cash", "debit_total": 100, "credit_total": 0, "balance": 100}]
    b = [{"account_id": "acc1", "account_code": "1000", "account_name": "Cash", "debit_total": 50, "credit_total": 0, "balance": 50}]
    merged = reporting_engine.merge_trial_balances([a, b])
    assert len(merged) == 1
    assert merged[0]["balance"] == 150


def test_merge_empty_lists() -> None:
    assert reporting_engine.merge_trial_balances([]) == []


def test_merge_multiple_accounts() -> None:
    a = [{"account_id": "1", "account_code": "A", "account_name": "A", "debit_total": 10, "credit_total": 0, "balance": 10}]
    b = [{"account_id": "2", "account_code": "B", "account_name": "B", "debit_total": 20, "credit_total": 0, "balance": 20}]
    merged = reporting_engine.merge_trial_balances([a, b])
    assert len(merged) == 2


# --- entity service cycle detection ---


def test_cycle_detection_direct() -> None:
    rows = [{"parent_company_id": HOLD, "child_company_id": SUB_A}]
    assert _would_create_cycle(rows, SUB_A, HOLD) is True


def test_cycle_detection_no_cycle() -> None:
    rows = [{"parent_company_id": HOLD, "child_company_id": SUB_A}]
    assert _would_create_cycle(rows, HOLD, SUB_B) is False


def test_cycle_detection_transitive() -> None:
    rows = [
        {"parent_company_id": HOLD, "child_company_id": SUB_A},
        {"parent_company_id": SUB_A, "child_company_id": SUB_B},
    ]
    assert _would_create_cycle(rows, SUB_B, HOLD) is True


def test_entity_service_rejects_self_link() -> None:
    with pytest.raises(ValueError, match="must differ"):
        entity_service.link_entities(ORG, parent_company_id=HOLD, child_company_id=HOLD, ownership_percent=100)


# --- consolidation engine ---


@patch("app.modules.erp.consolidation.engine.consolidation_engine.hierarchy_repository")
def test_consolidation_schema_not_ready(mock_h: MagicMock) -> None:
    mock_h.schema_ready.return_value = False
    result = run_consolidation(ORG, group_company_id=HOLD, fiscal_period_id="p1", dry_run=True)
    assert result.status == "failed"
    assert "schema" in (result.error or "")


@patch("app.modules.erp.consolidation.engine.consolidation_engine.reporting_engine.aggregate_entity_trial_balance")
@patch("app.modules.erp.consolidation.engine.consolidation_engine.intercompany_repository")
@patch("app.modules.erp.consolidation.engine.consolidation_engine.hierarchy_repository")
def test_consolidation_dry_run(mock_h: MagicMock, mock_ic: MagicMock, mock_tb: MagicMock) -> None:
    mock_h.schema_ready.return_value = True
    mock_h.list_children.return_value = [{"child_company_id": SUB_A}]
    mock_h.list_for_org.return_value = [{"parent_company_id": HOLD, "child_company_id": SUB_A, "ownership_percent": 100}]
    mock_ic.list_balances.return_value = []
    mock_ic.list_transactions.return_value = []
    mock_tb.return_value = [{"account_id": "a1", "account_code": "1000", "balance": 1000, "debit_total": 1000, "credit_total": 0}]
    result = run_consolidation(ORG, group_company_id=HOLD, fiscal_period_id="p1", dry_run=True)
    assert result.status == "dry_run"
    assert result.consolidated_rows >= 1


@patch("app.modules.erp.consolidation.engine.consolidation_engine.reporting_engine.aggregate_entity_trial_balance")
@patch("app.modules.erp.consolidation.engine.consolidation_engine.intercompany_repository")
@patch("app.modules.erp.consolidation.engine.consolidation_engine.hierarchy_repository")
def test_consolidation_with_ic_eliminations(mock_h: MagicMock, mock_ic: MagicMock, mock_tb: MagicMock) -> None:
    mock_h.schema_ready.return_value = True
    mock_h.list_children.return_value = []
    mock_h.list_for_org.return_value = []
    mock_ic.list_balances.return_value = [{"source_company_id": SUB_A, "target_company_id": SUB_B, "amount": 100_000}]
    mock_ic.list_transactions.return_value = []
    mock_tb.return_value = []
    result = run_consolidation(ORG, group_company_id=HOLD, fiscal_period_id="p1", company_ids=[HOLD], dry_run=True)
    assert len(result.eliminations) >= 1


# --- intercompany service ---


def test_intercompany_detect_mismatch() -> None:
    from app.modules.erp.consolidation.services.intercompany_service import intercompany_service

    with patch("app.modules.erp.consolidation.services.intercompany_service.intercompany_repository") as mock_repo:
        mock_repo.list_balances.return_value = [
            {"source_company_id": SUB_A, "target_company_id": SUB_B, "amount": 100_000},
            {"source_company_id": SUB_B, "target_company_id": SUB_A, "amount": -50_000},
        ]
        mismatches = intercompany_service.detect_mismatches(ORG)
        assert len(mismatches) == 1
        assert mismatches[0]["gap"] == 50_000


def test_intercompany_register_rejects_same_entity() -> None:
    from app.modules.erp.consolidation.services.intercompany_service import intercompany_service

    with pytest.raises(ValueError, match="must differ"):
        intercompany_service.register(
            ORG, source_company_id=HOLD, target_company_id=HOLD, transaction_type="loan", amount=100
        )


# --- events registry ---


def test_consolidation_events_registered() -> None:
    from app.modules.platform.events.bus.event_registry import ALL_EVENTS

    for evt in (
        "consolidation.completed",
        "consolidation.requested",
        "elimination.generated",
        "intercompany.created",
        "intercompany.mismatch.detected",
        "entity.closed",
    ):
        assert evt in ALL_EVENTS


def test_m33_materializes_consolidation_events() -> None:
    from app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline import MATERIALIZE_EVENT_TYPES

    assert "consolidation.completed" in MATERIALIZE_EVENT_TYPES
    assert "entity.closed" in MATERIALIZE_EVENT_TYPES


def test_event_consumer_wires_consolidation() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[4].joinpath("services", "event_consumers.py").read_text(encoding="utf-8")
    assert "_consume_consolidation_events" in text


# --- golden rule: no duplicate entity tables ---


def test_migration_extends_core_companies() -> None:
    from pathlib import Path

    mig = Path(__file__).resolve().parents[7] / "migrations" / "060_multi_entity_consolidation.sql"
    text = mig.read_text(encoding="utf-8")
    assert "ALTER TABLE core.companies" in text
    assert "CREATE TABLE IF NOT EXISTS erp.entity_hierarchy" in text
    assert "CREATE TABLE IF NOT EXISTS erp.entities" not in text


def test_no_duplicate_erp_branches_table() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[7].joinpath("migrations", "060_multi_entity_consolidation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS erp.branches" not in text
    assert "ALTER TABLE core.branches" in text


# --- module structure ---


@pytest.mark.parametrize(
    "rel_path",
    [
        "engine/consolidation_engine.py",
        "engine/elimination_engine.py",
        "engine/ownership_engine.py",
        "engine/currency_engine.py",
        "engine/reporting_engine.py",
        "services/entity_service.py",
        "services/intercompany_service.py",
        "services/consolidation_service.py",
        "repositories/hierarchy_repository.py",
        "repositories/intercompany_repository.py",
        "routes/consolidation_routes.py",
        "routes/intercompany_routes.py",
        "security/consolidation_guard.py",
        "events/consolidation_events.py",
    ],
)
def test_module_files_exist(rel_path: str) -> None:
    from pathlib import Path

    assert (Path(__file__).resolve().parents[1] / rel_path).exists()


def test_main_includes_consolidation_router() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[4].joinpath("main.py").read_text(encoding="utf-8")
    assert "erp_consolidation_router" in text


def test_journal_list_supports_company_filter() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[2].joinpath("journals", "routes", "journal_routes.py").read_text(encoding="utf-8")
    assert "company_id" in text


def test_object_context_resolves_company() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[4].joinpath("services", "object_context.py").read_text(encoding="utf-8")
    assert "company_id" in text
    assert "invoice_repository" in text


def test_approval_matrix_company_id() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[3].joinpath(
        "platform", "governance", "repositories", "approval_matrix_repository.py"
    ).read_text(encoding="utf-8")
    assert "company_id" in text


def test_treasury_ic_registration() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[2].joinpath(
        "treasury", "services", "transfer_service.py"
    ).read_text(encoding="utf-8")
    assert "_register_intercompany_if_cross_entity" in text


def test_fiscal_close_emits_entity_closed() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[2].joinpath(
        "fiscal", "services", "close_service.py"
    ).read_text(encoding="utf-8")
    assert "_emit_entity_closed" in text


def test_aggregation_engine_company_filter() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[2].joinpath(
        "reporting", "engine", "aggregation_engine.py"
    ).read_text(encoding="utf-8")
    assert "company_id" in text


@patch("app.modules.erp.consolidation.services.entity_service.hierarchy_repository")
def test_entity_service_build_tree(mock_repo: MagicMock) -> None:
    mock_repo.list_for_org.return_value = [
        {"parent_company_id": HOLD, "child_company_id": SUB_A, "ownership_percent": 100},
        {"parent_company_id": HOLD, "child_company_id": SUB_B, "ownership_percent": 80},
    ]
    tree = entity_service.build_tree(ORG)
    assert isinstance(tree, list)
    assert len(tree) >= 1


def test_consolidation_result_dataclass() -> None:
    r = ConsolidationResult(run_id="r1", status="completed", consolidated_rows=5)
    assert r.run_id == "r1"
    assert r.consolidated_rows == 5


@pytest.mark.parametrize(
    "pct,profit,expected_parent",
    [
        (100, 1_000_000, 1_000_000),
        (75, 400, 300),
        (51, 100, 51),
        (25, 400, 100),
    ],
)
def test_ownership_parametrized(pct: float, profit: float, expected_parent: float) -> None:
    r = ownership_engine.compute_ownership_split(subsidiary_profit=profit, ownership_percent=pct)
    assert r["parent_share"] == expected_parent


def test_elimination_job_preview() -> None:
    from app.modules.erp.consolidation.jobs.elimination_job import refresh_elimination_preview

    with patch("app.modules.erp.consolidation.jobs.elimination_job.intercompany_repository") as mock_repo:
        mock_repo.list_balances.return_value = [{"source_company_id": SUB_A, "target_company_id": SUB_B, "amount": 1}]
        mock_repo.list_transactions.return_value = []
        lines = refresh_elimination_preview(ORG)
        assert len(lines) == 1


def test_consolidation_job_wrapper() -> None:
    from app.modules.erp.consolidation.jobs.consolidation_job import run_consolidation_job

    with patch("app.modules.erp.consolidation.jobs.consolidation_job.consolidation_service") as mock_svc:
        from app.modules.erp.consolidation.engine.consolidation_engine import ConsolidationResult

        mock_svc.run.return_value = ConsolidationResult(run_id="j1", status="completed", consolidated_rows=3)
        out = run_consolidation_job(ORG, group_company_id=HOLD, fiscal_period_id="p1", actor_user_id="u1")
        assert out["run_id"] == "j1"


def test_currency_empty_list() -> None:
    assert currency_engine.validate_same_currency([]) is None
