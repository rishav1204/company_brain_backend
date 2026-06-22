import pytest

from app.modules.erp.treasury.ai.anomaly_detector import detect_payment_anomalies
from app.modules.erp.treasury.engine.cash_position_engine import build_position, compute_available_cash, compute_net_liquidity
from app.modules.erp.treasury.engine.liquidity_engine import bucket_cashflows
from app.modules.erp.treasury.engine.reconciliation_engine import score_match
from app.modules.erp.treasury.engine.treasury_engine import evaluate_payment_policy


def test_score_match_exact_amount_and_date() -> None:
    result = score_match(
        bank_amount=1000,
        bank_date="2026-06-01",
        bank_reference="INV-001",
        bank_description="Payment from Acme",
        bank_counterparty="Acme",
        ledger_debit=1000,
        ledger_credit=0,
        ledger_date="2026-06-01",
        ledger_reference="INV-001",
    )
    assert result["confidence_score"] >= 0.7
    assert "amount_exact" in result["factors"]


def test_compute_available_cash() -> None:
    assert compute_available_cash(credits=10000, debits=3000, restricted=500) == 6500.0


def test_net_liquidity() -> None:
    assert compute_net_liquidity(available_cash=100000, expected_collections=50000, upcoming_payments=80000) == 70000.0


def test_build_position() -> None:
    pos = build_position(
        accounts=[{"available": 50000}],
        expected_collections=20000,
        upcoming_payments=10000,
    )
    assert pos["net_liquidity"] == 60000.0


def test_liquidity_buckets() -> None:
    result = bucket_cashflows(
        inflows=[{"date": "2026-06-20", "amount": 1000}],
        outflows=[{"date": "2026-06-25", "amount": 500}],
    )
    assert "today" in result["buckets"]
    assert "30d" in result["buckets"]


def test_treasury_policy_cfo_threshold() -> None:
    policy = evaluate_payment_policy(amount=600_000, payment_type="vendor_payment")
    assert policy["requires_cfo"] is True
    assert "cfo" in policy["required_roles"]


def test_treasury_policy_dual_approval() -> None:
    policy = evaluate_payment_policy(amount=3_000_000, payment_type="vendor_payment")
    assert policy["requires_dual"] is True


def test_anomaly_duplicate_blocks() -> None:
    result = detect_payment_anomalies(
        amount=10000,
        beneficiary_ref="v1",
        history_amounts=[5000, 6000],
        recent_duplicate=True,
        beneficiary_verified=True,
    )
    assert result["block_execution"] is True
    assert "duplicate_payment" in result["flags"]


def test_anomaly_unverified_beneficiary_large_amount() -> None:
    result = detect_payment_anomalies(
        amount=200_000,
        beneficiary_ref="v1",
        history_amounts=[],
        recent_duplicate=False,
        beneficiary_verified=False,
    )
    assert result["block_execution"] is True


def test_anomaly_suspicious_timing_weekend() -> None:
    result = detect_payment_anomalies(
        amount=5000,
        beneficiary_ref="v1",
        history_amounts=[4000],
        recent_duplicate=False,
        beneficiary_verified=True,
        scheduled_date="2026-06-20",
    )
    assert "suspicious_timing" in result["flags"]


def test_treasury_policy_blocks_without_cfo() -> None:
    from app.modules.erp.treasury.services.treasury_policy_service import treasury_policy_service

    policy = treasury_policy_service.check_payment(
        org_id="00000000-0000-0000-0000-000000000001",
        amount=600_000,
        payment_type="vendor_payment",
        roles=["treasury_manager"],
    )
    assert policy["allowed"] is False
    assert "cfo" in policy["missing_roles"]


def test_bank_rail_stub_execute() -> None:
    from app.modules.erp.treasury.services.bank_rail_service import bank_rail_service
    from unittest.mock import patch

    with patch(
        "app.modules.erp.banking.services.bank_rail_service.bank_account_repository.get",
        return_value={"metadata": {"provider": "stub_bank"}},
    ):
        with patch(
            "app.modules.erp.banking.services.bank_rail_service.connector_registry.resolve",
        ) as resolve:
            from app.modules.platform.integrations.connectors.banks.stub_bank_connector import StubBankConnector

            resolve.return_value = StubBankConnector()
            result = bank_rail_service.execute_payment(
                "org",
                bank_account_id="bank-1",
                amount=1000,
                reference="TPR-1",
                beneficiary_ref="vendor-1",
            )
    assert result["status"] == "completed"
