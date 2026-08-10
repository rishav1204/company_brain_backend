from __future__ import annotations

from datetime import date, timedelta


def detect_dead_stock(movements: list[dict], *, as_of: str | None = None, days: int = 90) -> list[dict]:
    cutoff = date.fromisoformat(str(as_of or date.today().isoformat())[:10]) - timedelta(days=days)
    last_move: dict[str, str] = {}
    for m in movements:
        key = f"{m.get('item_id')}:{m.get('warehouse_id')}"
        mdate = str(m.get("movement_date") or "")[:10]
        if mdate >= str(last_move.get(key, "")):
            last_move[key] = mdate
    dead = []
    for key, last in last_move.items():
        if date.fromisoformat(last) < cutoff:
            item_id, warehouse_id = key.split(":", 1)
            dead.append({"item_id": item_id, "warehouse_id": warehouse_id, "last_movement_date": last, "days_idle": days})
    return dead
