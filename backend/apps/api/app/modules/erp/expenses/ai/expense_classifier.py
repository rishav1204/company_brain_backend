from __future__ import annotations

from datetime import datetime


def classify_expense(extracted_data: dict) -> str:
    text = " ".join(
        str(extracted_data.get(k) or "") for k in ("merchant", "vendor", "description", "category_hint", "raw_text")
    ).lower()
    if any(w in text for w in ("hotel", "taj", "inn", "lodging")):
        return "hotel"
    if any(w in text for w in ("uber", "ola", "taxi", "cab", "flight", "airline", "irctc", "train")):
        return "travel"
    if any(w in text for w in ("restaurant", "cafe", "meal", "food", "swiggy", "zomato")):
        return "meal"
    if any(w in text for w in ("petrol", "fuel", "diesel", "hp ", "ioc")):
        return "fuel"
    if any(w in text for w in ("airtel", "jio", "vodafone", "mobile", "internet", "broadband")):
        return "internet" if "internet" in text or "broadband" in text else "mobile"
    return str(extracted_data.get("category_hint") or extracted_data.get("expense_type") or "miscellaneous").lower()


def fraud_score(extracted_data: dict, *, amount: float) -> float:
    score = 0.0
    conf = float(extracted_data.get("confidence_score") or extracted_data.get("aggregate_confidence") or 1)
    if conf < 0.6:
        score += 30
    if amount > 0 and str(int(amount)).endswith("999"):
        score += 15
    try:
        d = str(extracted_data.get("date") or extracted_data.get("receipt_date") or "")[:10]
        if d:
            wd = datetime.fromisoformat(d).weekday()
            if wd >= 5:
                score += 10
    except Exception:
        pass
    return min(100, score)
