from __future__ import annotations

from app.modules.erp.gl.validators.double_entry_validator import validate_double_entry


def validate_journal_balance(lines: list[dict]) -> tuple[float, float]:
    """Ensure debits = credits for journal lines."""
    return validate_double_entry(lines)
