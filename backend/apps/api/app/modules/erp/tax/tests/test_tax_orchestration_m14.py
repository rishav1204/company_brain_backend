from app.modules.finance_os.domain_intelligence.tax.compliance_assistant import answer_compliance_question
from app.modules.finance_os.domain_intelligence.tax.gst_copilot import answer_gst_question
from app.modules.finance_os.domain_intelligence.tax.tax_risk_engine import assess_tax_risks
from app.services.event_consumers import _handle_tax_workflow_approval


def test_tax_workflow_approval_missing_id() -> None:
    assert _handle_tax_workflow_approval("org", {"entity_type": "other"}) is False


def test_gst_copilot_liability() -> None:
    result = answer_gst_question(
        question="Why is GST liability high?",
        returns=[{"payload": {"net_liability": 50000}}],
        transactions=[{"gst_type": "sales"}],
        itc_summary={"available": 10000},
    )
    assert "liability" in result["answer"].lower()


def test_compliance_vendor_mismatch() -> None:
    result = answer_compliance_question(
        question="Which vendors cause ITC mismatches?",
        reconciliations=[{"match_status": "mismatch", "metadata": {"vendor_gstin": "27TEST1234F1Z5"}}],
    )
    assert "vendor" in result["answer"].lower()


def test_tax_risk_assessment() -> None:
    result = assess_tax_risks(
        reconciliations=[{"match_status": "mismatch"}],
        returns=[{"status": "draft"}],
        calendar=[{"status": "pending"}] * 4,
    )
    assert result["risk_score"] > 0
