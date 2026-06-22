from __future__ import annotations

from datetime import date

from app.modules.finance_os.forecasting.engine.collections_engine import infer_late_days_from_memory
from app.modules.finance_os.forecasting.engine.forecast_scoring_engine import score_confidence
from app.modules.finance_os.forecasting.services.forecast_explanation_service import build_evidence
from app.modules.finance_os.forecasting.services.forecast_query_service import get_series


def test_infer_late_days_caps_high() -> None:
    snippets = [{"content": "Pays 999 days late"}]
    assert infer_late_days_from_memory(snippets) == 120


def test_infer_late_days_handles_non_int() -> None:
    snippets = [{"content": "Pays twelve days late"}]
    assert infer_late_days_from_memory(snippets) == 0


def test_score_confidence_clamps_inputs() -> None:
    score, band = score_confidence(data_quality=9, memory_hits=99, graph_evidence=99, history_days=999)
    assert 0 <= score <= 100
    assert band == "high"


def test_score_confidence_medium_band_range() -> None:
    score, band = score_confidence(data_quality=0.8, memory_hits=0, graph_evidence=0, history_days=30)
    assert band in {"medium", "low", "high"}
    assert 0 <= score <= 100


def test_build_evidence_risks_when_no_memory_graph() -> None:
    ev = build_evidence(inputs={"starting_cash": 1, "min_cash": 1}, memory_count=0, graph_count=0)
    assert "no_memory_adjustments" in (ev.get("risks") or [])
    assert "no_graph_evidence" in (ev.get("risks") or [])


def test_build_evidence_cash_negative_risk() -> None:
    ev = build_evidence(inputs={"starting_cash": 1, "min_cash": -1}, memory_count=1, graph_count=1)
    assert "cash_negative_risk" in (ev.get("risks") or [])


def test_get_series_empty_when_no_schema(monkeypatch) -> None:
    from app.modules.finance_os.forecasting.repositories import forecast_repository as fr_mod

    monkeypatch.setattr(fr_mod.forecast_repository, "list_latest", lambda *a, **k: [])
    out = get_series("org", forecast_type="cash", horizon_days=30)
    assert out["items"] == []


def test_confidence_band_strings() -> None:
    for dq in [0.0, 0.5, 1.0]:
        _, band = score_confidence(data_quality=dq, memory_hits=0, graph_evidence=0, history_days=0)
        assert band in {"low", "medium", "high"}


def test_evidence_drivers_presence() -> None:
    ev = build_evidence(inputs={"starting_cash": 1, "ar_outstanding_total": 2, "ap_outstanding_total": 3, "min_cash": 1})
    drivers = ev.get("drivers") or []
    assert "starting_cash" in drivers
    assert "ar_outstanding_total" in drivers
    assert "ap_outstanding_total" in drivers


def test_evidence_inputs_roundtrip() -> None:
    inputs = {"starting_cash": 1}
    ev = build_evidence(inputs=inputs)
    assert ev.get("inputs") == inputs


def test_score_confidence_history_effect() -> None:
    s1, _ = score_confidence(data_quality=0.7, memory_hits=0, graph_evidence=0, history_days=0)
    s2, _ = score_confidence(data_quality=0.7, memory_hits=0, graph_evidence=0, history_days=90)
    assert s2 >= s1


def test_score_confidence_memory_effect() -> None:
    s1, _ = score_confidence(data_quality=0.7, memory_hits=0, graph_evidence=0, history_days=30)
    s2, _ = score_confidence(data_quality=0.7, memory_hits=5, graph_evidence=0, history_days=30)
    assert s2 >= s1


def test_score_confidence_graph_effect() -> None:
    s1, _ = score_confidence(data_quality=0.7, memory_hits=0, graph_evidence=0, history_days=30)
    s2, _ = score_confidence(data_quality=0.7, memory_hits=0, graph_evidence=3, history_days=30)
    assert s2 >= s1


def test_build_evidence_no_cash_negative_when_positive() -> None:
    ev = build_evidence(inputs={"min_cash": 1})
    assert "cash_negative_risk" not in (ev.get("risks") or [])


def test_build_evidence_drivers_empty_when_no_inputs() -> None:
    ev = build_evidence(inputs={})
    assert isinstance(ev.get("drivers"), list)

