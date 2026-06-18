from app.modules.erp.accounts_receivable.ai.collection_predictor import forecast_collections


def test_collection_forecast() -> None:
    result = forecast_collections([
        {"id": "i1", "status": "issued", "total_amount": 10000, "paid_amount": 0, "due_date": "2020-01-01"},
    ])
    assert "forecast" in result
    assert result["forecast"]["7_days"] >= 0
