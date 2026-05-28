from __future__ import annotations

from datetime import datetime, time, timezone


def in_quiet_hours(quiet_hours: dict | None) -> bool:
    if not quiet_hours:
        return False
    start_s = quiet_hours.get("start")
    end_s = quiet_hours.get("end")
    if not start_s or not end_s:
        return False
    try:
        now = datetime.now(timezone.utc).time()
        start = time.fromisoformat(str(start_s))
        end = time.fromisoformat(str(end_s))
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end
    except (TypeError, ValueError):
        return False
