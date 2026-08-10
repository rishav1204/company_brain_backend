"""CI gate for implementation completeness audit output.

The audit artifact is produced by implementation_completeness_audit.py and
lives under docs/. When it is absent the `completeness_audit_data` fixture
skips, so these gates only assert against a real audit run.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]


def test_critical_stubs_zero(completeness_audit_data: dict[str, Any]):
    assert completeness_audit_data["stubs"]["critical_count"] == 0


def test_legacy_shims_are_thin():
    app = REPO / "apps" / "api" / "app"
    handlers = app / "services" / "event_consumers_handlers.py"
    repos = app / "services" / "repositories.py"
    # Shims may include __getattr__/__dir__ housekeeping; keep them well under a page.
    assert len(handlers.read_text(encoding="utf-8").splitlines()) < 25
    assert len(repos.read_text(encoding="utf-8").splitlines()) < 25


def test_scores_present(completeness_audit_data: dict[str, Any]):
    scores = completeness_audit_data["scores"]
    assert scores["code_quality"] >= 7
    assert scores["testability"] >= 7
