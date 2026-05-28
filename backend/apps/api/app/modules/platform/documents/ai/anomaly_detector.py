from __future__ import annotations


def detect_anomalies(extracted_data: dict) -> list[dict]:
    findings: list[dict] = []
    total = float(extracted_data.get("total_amount") or 0)
    if total > 10_000_000:
        findings.append({"type": "high_invoice_amount", "severity": "high", "detail": "Invoice amount exceeds threshold"})
    return findings
