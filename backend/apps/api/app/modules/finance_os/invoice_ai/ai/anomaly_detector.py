from __future__ import annotations

from typing import Any


def detect_anomalies(
    *,
    total_amount: float,
    vendor_avg: float | None,
    vendor_std: float | None,
    extraction_confidence: float,
    duplicate_status: str,
) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []

    if extraction_confidence < 0.5:
        anomalies.append(
            {
                "anomaly_type": "low_extraction_confidence",
                "anomaly_score": round(1 - extraction_confidence, 2),
                "severity": "high" if extraction_confidence < 0.35 else "medium",
                "description": "OCR/extraction confidence below threshold",
            }
        )

    if duplicate_status in ("suspected", "confirmed"):
        anomalies.append(
            {
                "anomaly_type": "duplicate_invoice",
                "anomaly_score": 0.9 if duplicate_status == "confirmed" else 0.65,
                "severity": "high" if duplicate_status == "confirmed" else "medium",
                "description": f"Duplicate invoice status: {duplicate_status}",
            }
        )

    if vendor_avg and vendor_avg > 0 and total_amount > vendor_avg * 2:
        z = (total_amount - vendor_avg) / (vendor_std or vendor_avg * 0.5)
        if z > 2:
            anomalies.append(
                {
                    "anomaly_type": "amount_spike",
                    "anomaly_score": min(1.0, z / 5),
                    "severity": "high" if z > 3 else "medium",
                    "description": f"Invoice amount {total_amount:.2f} exceeds vendor average {vendor_avg:.2f}",
                }
            )

    return anomalies
