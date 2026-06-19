from __future__ import annotations


def classify_asset(description: str) -> dict:
    text = str(description or "").lower()
    if any(w in text for w in ("laptop", "computer", "dell", "latitude", "macbook", "server")):
        return {"category_code": "COMPUTERS", "category_hint": "Computers", "useful_life_months": 36}
    if any(w in text for w in ("furniture", "chair", "desk", "table")):
        return {"category_code": "FURNITURE", "category_hint": "Furniture", "useful_life_months": 60}
    if any(w in text for w in ("vehicle", "car", "truck", "bike")):
        return {"category_code": "VEHICLES", "category_hint": "Vehicles", "useful_life_months": 60}
    if any(w in text for w in ("building", "office space", "warehouse")):
        return {"category_code": "BUILDINGS", "category_hint": "Buildings", "useful_life_months": 240}
    if any(w in text for w in ("machine", "machinery", "equipment", "plant")):
        return {"category_code": "MACHINERY", "category_hint": "Machinery", "useful_life_months": 120}
    if any(w in text for w in ("software", "license", "saas")):
        return {"category_code": "SOFTWARE", "category_hint": "Software", "useful_life_months": 36}
    return {"category_code": "COMPUTERS", "category_hint": "miscellaneous", "useful_life_months": 36}
