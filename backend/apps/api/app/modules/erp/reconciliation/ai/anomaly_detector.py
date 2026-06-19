from __future__ import annotations

from app.modules.erp.reconciliation.engine.anomaly_engine import detect_reconciliation_anomalies


def detect_anomalies(*, bank_tx: dict, candidates: list[dict] | None = None, history_amounts: list[float] | None = None) -> list[dict]:
    return detect_reconciliation_anomalies(bank_tx=bank_tx, candidates=candidates, history_amounts=history_amounts)
