from app.modules.erp.tax.ai.tds_copilot import answer_tds_question
from app.modules.erp.tax.ai.tds_error_detector import detect_tds_errors
from app.modules.erp.tax.ai.tds_return_reviewer import review_return_payload
from app.modules.erp.tax.ai.tds_section_recommender import recommend_section
from app.modules.erp.tax.ai.tax_risk_engine import assess_tax_risks
from app.modules.erp.tax.engine.form16a_pdf_engine import render_form16a_pdf


def test_recommend_section_professional() -> None:
    result = recommend_section(payment_type="professional", amount=50000)
    assert result["section_code"] == "194J"


def test_detect_missing_pan_escalation() -> None:
    txs = [{"id": "1", "section_code": "194J", "gross_amount": 100000, "tds_amount": 5000, "status": "calculated"}]
    result = detect_tds_errors(transactions=txs, vendor_pan=None, rules=[{"section_code": "194J", "rate_pan": 10, "rate_no_pan": 20}])
    assert any(f["issue"] == "missing_pan_escalation" for f in result["flags"])


def test_tds_copilot_liability() -> None:
    result = answer_tds_question(question="What is my TDS liability?", liability={"total_liability": 50000, "transaction_count": 3})
    assert "50,000" in result["answer"]


def test_return_reviewer_empty() -> None:
    result = review_return_payload(payload={"sections": [], "summary": {"total_tax": 0}}, form_type="26Q")
    assert result["ready_to_file"] is False


def test_tax_risk_tds_liability() -> None:
    result = assess_tax_risks(reconciliations=[], returns=[], calendar=[], tds_liability={"total_liability": 200000})
    assert any(r["type"] == "tds_liability_pending" for r in result["risks"])


def test_form16a_pdf_render() -> None:
    pdf = render_form16a_pdf({
        "vendor_name": "Acme Corp",
        "pan": "ABCDE1234F",
        "financial_year": "2025-2026",
        "quarter": "Q1",
        "gross_total": 100000,
        "tds_total": 10000,
        "deductions": [{"section_code": "194J", "gross_amount": 100000, "tds_amount": 10000, "deduction_date": "2025-05-01"}],
    })
    assert pdf[:4] == b"%PDF"
