from __future__ import annotations

import re


def _parse_amount(raw: str) -> float:
    try:
        return float(str(raw).replace(",", ""))
    except ValueError:
        return 0.0


def extract(text: str) -> dict:
    """Extract receipt fields from OCR text."""
    data: dict = {"raw_text": text}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        data["merchant"] = lines[0][:255]
    amount_match = re.search(r"(?:total|amount|rs\.?|inr)\s*[:\-]?\s*([\d,]+\.?\d*)", text, re.I)
    if not amount_match:
        amount_match = re.search(r"([\d,]+\.\d{2})", text)
    if amount_match:
        data["amount"] = _parse_amount(amount_match.group(1))
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if not date_match:
        date_match = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", text)
    if date_match:
        data["date"] = date_match.group(1).replace("/", "-")
    lower = text.lower()
    if "hotel" in lower:
        data["category_hint"] = "hotel"
    elif "taxi" in lower or "uber" in lower:
        data["category_hint"] = "travel"
    elif "restaurant" in lower or "cafe" in lower:
        data["category_hint"] = "meal"
    return data
