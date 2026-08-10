from __future__ import annotations

from app.modules.erp.query_services import domain_calc


def detect_anomalies(*, bank_tx: dict, candidates: list[dict] | None = None, history_amounts: list[float] | None = None) -> list[dict]:
    return domain_calc.detect_reconciliation_anomalies(
        bank_tx=bank_tx,
        candidates=candidates,
        history_amounts=history_amounts,
    )
