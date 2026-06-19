import pytest

from app.modules.erp.treasury.ai.anomaly_detector import detect_payment_anomalies
from app.modules.erp.treasury.engine.reconciliation_engine import rank_subledger_candidates, score_match
from app.modules.erp.treasury.services.beneficiary_verification_service import beneficiary_verification_service
from app.modules.platform.integrations.connectors.banks.stub_bank_connector import StubBankConnector
from app.modules.workflows.services.step_executors import _execute_payment_execution


def test_stub_bank_execute_payment() -> None:
    connector = StubBankConnector()
    result = connector.execute_payment(amount=1000, reference="TPR-TEST", beneficiary={"ref": "vendor-1"})
    assert result["status"] == "completed"
    assert result.get("bank_reference")


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


def test_anomaly_new_beneficiary_large_blocks() -> None:
    result = detect_payment_anomalies(
        amount=600_000,
        beneficiary_ref="v1",
        history_amounts=[],
        recent_duplicate=False,
        beneficiary_verified=True,
        new_beneficiary=True,
    )
    assert result["block_execution"] is True
    assert "new_beneficiary" in result["flags"]


def test_subledger_reconciliation_match() -> None:
    bank_tx = {
        "amount": 25000,
        "transaction_date": "2026-06-01",
        "transaction_reference": "RCP-001",
        "description": "Payment from Acme",
        "counterparty_ref": "cust-1",
        "transaction_type": "credit",
    }
    candidates = [{
        "id": "r1",
        "target_type": "ar_receipt",
        "amount": 25000,
        "date": "2026-06-01",
        "reference": "RCP-001",
        "counterparty_ref": "cust-1",
    }]
    ranked = rank_subledger_candidates(bank_tx, candidates)
    assert ranked[0]["confidence_score"] >= 0.7
    assert ranked[0]["match_target_type"] == "ar_receipt"


def test_beneficiary_verification_missing_bank_account() -> None:
    result = beneficiary_verification_service.verify_vendor_payment("org", vendor_id="v1", vendor_bank_account_id=None)
    assert result["verified"] is False


def test_payment_execution_step_missing_id() -> None:
    result = _execute_payment_execution(org_id="org", instance={"id": "wf-1", "metadata": {}}, step={}, trace_id=None)
    assert result["status"] == "failed"


def test_score_match_subledger_reference() -> None:
    result = score_match(
        bank_amount=1000,
        bank_date="2026-06-01",
        bank_reference="INV-99",
        bank_description="Vendor payment",
        bank_counterparty="vendor-a",
        ledger_debit=1000,
        ledger_credit=0,
        ledger_date="2026-06-01",
        ledger_reference="INV-99",
        ledger_counterparty="vendor-a",
    )
    assert result["confidence_score"] >= 0.65
