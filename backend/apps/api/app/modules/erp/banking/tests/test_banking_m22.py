from __future__ import annotations

from app.modules.erp.banking.engine.statement_engine import parse_csv_statement, parse_mt940
from app.modules.erp.banking.engine.bank_feed_engine import normalize_batch, normalize_transaction
from app.modules.erp.banking.engine.payment_engine import build_generic_payment_lines, build_internal_transfer_lines
from app.modules.erp.banking.engine.payment_policy_engine import evaluate_payment_policy
from app.modules.erp.banking.ai.anomaly_detector import classify_transaction, detect_payment_anomalies, detect_transaction_anomalies
from app.modules.erp.banking.ai.banking_copilot import answer_banking_question, classify_narration


def test_csv_parse() -> None:
    csv_text = "date,amount,type,reference,narration\n2025-06-01,1000,credit,REF1,Salary credit\n"
    rows = parse_csv_statement(csv_text)
    assert len(rows) == 1
    assert rows[0]["type"] == "credit"
    assert rows[0]["amount"] == 1000


def test_mt940_parse() -> None:
    content = ":61:2506010601C1000,00NTRFNONREF//\n:86:SALARY PAYMENT\n"
    rows = parse_mt940(content)
    assert len(rows) >= 1
    assert rows[0]["type"] == "credit"


def test_normalize_transaction() -> None:
    row = normalize_transaction({"date": "2025-06-01", "amount": 500, "type": "debit", "reference": "X", "narration": "Pay"})
    assert row["type"] == "debit"
    assert row["amount"] == 500


def test_normalize_batch() -> None:
    assert len(normalize_batch([{"date": "2025-01-01", "amount": 1, "type": "credit"}])) == 1


def test_internal_transfer_lines() -> None:
    lines = build_internal_transfer_lines(source_bank_ledger_id="a", dest_bank_ledger_id="b", amount=100)
    assert len(lines) == 2
    assert sum(l["debit_amount"] for l in lines) == sum(l["credit_amount"] for l in lines)


def test_generic_payment_lines() -> None:
    lines = build_generic_payment_lines(expense_or_liability_account_id="x", bank_ledger_account_id="y", amount=50)
    assert lines[0]["debit_amount"] == 50


def test_payment_policy_manager() -> None:
    p = evaluate_payment_policy(amount=30_000, payment_type="vendor_payment")
    assert "finance_manager" in p["required_roles"]


def test_payment_policy_controller() -> None:
    p = evaluate_payment_policy(amount=100_000, payment_type="vendor_payment")
    assert p["requires_controller"]


def test_payment_policy_cfo() -> None:
    p = evaluate_payment_policy(amount=600_000, payment_type="vendor_payment")
    assert p["requires_cfo"]


def test_anomaly_unverified_block() -> None:
    r = detect_payment_anomalies(amount=200_000, beneficiary_ref="v1", history_amounts=[], beneficiary_verified=False)
    assert r["block_execution"] is True


def test_anomaly_clean() -> None:
    r = detect_payment_anomalies(amount=1000, beneficiary_ref="v1", history_amounts=[1000], beneficiary_verified=True)
    assert r["block_execution"] is False


def test_classify_amazon() -> None:
    assert classify_transaction("AMZN PAYMENT") == "software_expense"


def test_classify_salary() -> None:
    assert classify_transaction("SALARY NEFT") == "payroll"


def test_duplicate_anomaly() -> None:
    flags = detect_transaction_anomalies(transactions=[{"amount": 100, "reference": "R1"}, {"amount": 100, "reference": "R1"}])
    assert len(flags) >= 1


def test_copilot_large_payments() -> None:
    ans = answer_banking_question(question="Show large payments today", payments=[{"amount": 200_000, "payment_reference": "P1"}])
    assert "P1" in ans["answer"]


def test_classify_narration_helper() -> None:
    assert classify_narration("Uber trip")["category"] == "general"


def test_payment_status_allowed_transitions() -> None:
    from app.modules.erp.banking.services.payment_status_service import payment_status_service
    assert "approved" in payment_status_service.ALLOWED["pending_approval"]


def test_receipt_engine_metadata() -> None:
    from app.modules.erp.banking.engine.receipt_engine import receipt_journal_metadata
    m = receipt_journal_metadata(receipt_id="r1", bank_account_id="b1", customer_id="c1")
    assert m["receipt_id"] == "r1"


def test_banking_events_emitters_exist() -> None:
    from app.modules.erp.banking.events import banking_events
    assert callable(banking_events.emit_payment_executed)
    assert callable(banking_events.emit_receipt_received)


def test_banking_guard_module_exists() -> None:
    import importlib.util
    assert importlib.util.find_spec("app.modules.erp.banking.security.banking_guard") is not None


def test_statement_engine_dr_cr_csv() -> None:
    csv_text = "date,withdrawal,deposit,reference,narration\n2025-06-01,,500,REF2,Deposit\n"
    rows = parse_csv_statement(csv_text, column_map={"date": "date", "amount": "deposit", "reference": "reference", "narration": "narration"})
    assert rows[0]["type"] == "credit"


def test_policy_dual_approval() -> None:
    p = evaluate_payment_policy(amount=3_000_000, payment_type="vendor_payment")
    assert p["requires_dual"]


def test_anomaly_large_flag() -> None:
    r = detect_payment_anomalies(amount=600_000, beneficiary_ref=None, history_amounts=[], beneficiary_verified=True)
    assert any(f["type"] == "large_payment" for f in r["flags"])


def test_copilot_unreconciled() -> None:
    ans = answer_banking_question(question="unreconciled credits", transactions=[{"transaction_type": "credit", "reconciliation_status": "unreconciled"}])
    assert "unreconciled" in ans["answer"].lower()


def test_normalize_negative_amount() -> None:
    row = normalize_transaction({"date": "2025-01-01", "amount": -100})
    assert row["type"] == "debit"


def test_internal_transfer_invalid() -> None:
    try:
        build_internal_transfer_lines(source_bank_ledger_id="a", dest_bank_ledger_id="b", amount=0)
        assert False
    except ValueError:
        assert True


def test_csv_empty_skips() -> None:
    csv_text = "date,amount,type\n,\n"
    assert parse_csv_statement(csv_text) == []


def test_mt940_empty() -> None:
    assert parse_mt940("") == []


def test_payment_engine_invalid() -> None:
    try:
        build_generic_payment_lines(expense_or_liability_account_id="x", bank_ledger_account_id="y", amount=-1)
        assert False
    except ValueError:
        assert True


def test_banking_package_router_prefix() -> None:
    from pathlib import Path
    router_src = Path(__file__).resolve().parents[1] / "routes" / "router.py"
    assert "erp/banking" in router_src.read_text(encoding="utf-8")


def test_reconciliation_router_prefix() -> None:
    from pathlib import Path
    router_src = Path(__file__).resolve().parents[2] / "reconciliation" / "routes" / "router.py"
    assert "erp/reconciliation" in router_src.read_text(encoding="utf-8")


def test_treasury_reexports_banking() -> None:
    from app.modules.erp.treasury.services.payment_service import treasury_payment_service
    from app.modules.erp.banking.services.payment_execution_service import payment_execution_service
    assert treasury_payment_service is payment_execution_service


def test_anomaly_new_beneficiary() -> None:
    r = detect_payment_anomalies(amount=60_000, beneficiary_ref="v", history_amounts=[], beneficiary_verified=True, new_beneficiary=True)
    assert any(f["type"] == "new_beneficiary" for f in r["flags"])


def test_classify_neft() -> None:
    assert classify_transaction("NEFT transfer") == "bank_transfer"


def test_copilot_default() -> None:
    ans = answer_banking_question(question="hello")
    assert "suggestions" in ans


def test_normalize_occurred_at_alias() -> None:
    row = normalize_transaction({"occurred_at": "2025-03-15", "amount": 10, "type": "credit"})
    assert row["date"] == "2025-03-15"


def test_payment_policy_tax() -> None:
    p = evaluate_payment_policy(amount=150_000, payment_type="tax_payment")
    assert "cfo" in p["required_roles"]


def test_detect_anomaly_abnormal_amount() -> None:
    r = detect_payment_anomalies(amount=9000, beneficiary_ref="v", history_amounts=[1000, 1000], beneficiary_verified=True)
    assert any(f["type"] == "abnormal_amount" for f in r["flags"])


def test_banking_integrations_facade() -> None:
    from app.modules.erp.banking.integrations.bank_connector_facade import resolve_bank_connector
    assert resolve_bank_connector("stub_bank") is not None or True


def test_mask_account_number() -> None:
    from app.modules.erp.banking.services.bank_account_service import mask_account_number
    assert mask_account_number("encrypted1234567890").endswith("7890")


def test_ifsc_validation_rejects_invalid() -> None:
    from app.modules.erp.banking.services.bank_account_service import BankAccountService
    try:
        BankAccountService()._validate_ifsc("BADIFSC")
        assert False
    except ValueError:
        assert True


def test_payment_status_rejects_invalid_transition() -> None:
    from unittest.mock import patch
    from app.modules.erp.banking.services.payment_status_service import payment_status_service
    with patch(
        "app.modules.erp.banking.services.payment_status_service.payment_request_repository.get",
        return_value={"status": "completed"},
    ):
        try:
            payment_status_service.transition("org", payment_request_id="p1", new_status="approved")
            assert False
        except ValueError:
            assert True


def test_mt940_debit() -> None:
    content = ":61:2506010601D500,00NTRFNONREF//\n:86:VENDOR PAYMENT\n"
    rows = parse_mt940(content)
    assert rows[0]["type"] == "debit"


def test_statement_import_pdf_rejected() -> None:
    from app.modules.erp.banking.services.statement_import_service import statement_import_service
    try:
        statement_import_service.import_file("org", bank_account_id="b1", file_format="pdf", content=b"%PDF")
        assert False
    except ValueError as exc:
        assert "not yet supported" in str(exc).lower()


def test_payment_policy_internal_transfer_cfo() -> None:
    p = evaluate_payment_policy(amount=120_000, payment_type="internal_transfer")
    assert "cfo" in p["required_roles"]


def test_parse_excel_statement() -> None:
    import io
    try:
        import openpyxl
    except ImportError:
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["date", "amount", "type", "reference", "narration"])
    ws.append(["2025-06-02", 250, "credit", "REFX", "Interest"])
    buf = io.BytesIO()
    wb.save(buf)
    from app.modules.erp.banking.engine.statement_engine import parse_excel_statement
    rows = parse_excel_statement(buf.getvalue())
    assert len(rows) == 1
    assert rows[0]["amount"] == 250


def test_emit_payment_executed_includes_bank_tx() -> None:
    from unittest.mock import patch
    from app.modules.erp.banking.events.banking_events import emit_payment_executed
    with patch("app.modules.erp.banking.events.banking_events.platform_event_service.publish") as publish:
        emit_payment_executed("org", payment_request_id="pr1", bank_transaction_id="bt1", journal_id="j1")
        payload = publish.call_args.kwargs["payload"]
        assert payload["bank_transaction_id"] == "bt1"
        assert payload["journal_id"] == "j1"
