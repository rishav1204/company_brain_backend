"""CI gate for implementation completeness audit output."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "ENTERPRISE_CODE_QUALITY_REVIEW_DATA.json"


def test_implementation_completeness_audit_data_exists():
    assert DATA.is_file(), "Run backend/scripts/implementation_completeness_audit.py"


def test_critical_stubs_zero():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert data["stubs"]["critical_count"] == 0


def test_legacy_shims_are_thin():
    app = REPO / "apps" / "api" / "app"
    handlers = app / "services" / "event_consumers_handlers.py"
    repos = app / "services" / "repositories.py"
    assert len(handlers.read_text(encoding="utf-8").splitlines()) < 10
    assert len(repos.read_text(encoding="utf-8").splitlines()) < 10


def test_scores_present():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    scores = data["scores"]
    assert scores["code_quality"] >= 7
    assert scores["testability"] >= 7
