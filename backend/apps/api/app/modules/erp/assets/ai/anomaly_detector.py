from __future__ import annotations


def detect_anomalies(assets: list[dict]) -> list[dict]:
    anomalies: list[dict] = []
    seen: dict[str, int] = {}
    for asset in assets:
        key = f"{asset.get('asset_name')}|{asset.get('cost')}"
        seen[key] = seen.get(key, 0) + 1
        if str(asset.get("status")) == "active" and float(asset.get("book_value") or 0) <= 0:
            anomalies.append({"asset_id": asset.get("id"), "type": "zero_book_value", "severity": "warning"})
    for key, count in seen.items():
        if count > 1:
            anomalies.append({"type": "duplicate_asset", "key": key, "count": count, "severity": "warning"})
    return anomalies
