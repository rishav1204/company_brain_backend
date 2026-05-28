from app.modules.platform.documents.ai.confidence_engine import confidence_engine


def test_confidence_engine_aggregate() -> None:
    field_scores = confidence_engine.score_fields({"invoice_number": "INV-1", "total_amount": 1200})
    score = confidence_engine.aggregate(field_scores)
    assert score > 0.85
