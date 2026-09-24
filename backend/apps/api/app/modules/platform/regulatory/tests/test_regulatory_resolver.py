"""Unit tests for regulatory resolver matching / rate logic without DB when possible."""

from __future__ import annotations

from app.modules.platform.regulatory.repositories.regulatory_repository import (
    RegulatoryRepository,
)
from app.modules.erp.tax.engine.tds_engine import resolve_effective_rate


def test_match_penalty_prefers_prefix() -> None:
    repo = RegulatoryRepository()
    rows = [
        {"compliance_code_pattern": "*", "formula_code": "generic", "daily_fee": 50},
        {"compliance_code_pattern": "GST%", "formula_code": "gst", "daily_fee": 100},
        {"compliance_code_pattern": "GSTR3B", "formula_code": "exact", "daily_fee": 1},
    ]
    m = repo._match_penalty(rows, "GSTR3B")
    assert m and m["formula_code"] == "exact"
    m2 = repo._match_penalty(rows, "GST_PAYMENT")
    assert m2 and m2["formula_code"] == "gst"


def test_resolve_effective_rate_uses_floor_from_resolver(monkeypatch) -> None:
    from app.modules.platform.regulatory.services import regulatory_resolver as rr_mod

    monkeypatch.setattr(
        rr_mod.regulatory_resolver,
        "resolve_param_numeric",
        lambda *a, **k: 20.0,
    )
    assert resolve_effective_rate(rate_pan=10, rate_no_pan=5, pan_present=False) == 20.0
    assert resolve_effective_rate(rate_pan=10, rate_no_pan=25, pan_present=False) == 25.0
    assert resolve_effective_rate(rate_pan=10, rate_no_pan=5, pan_present=True) == 10.0
