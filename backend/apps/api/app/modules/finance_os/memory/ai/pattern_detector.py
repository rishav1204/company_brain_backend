from __future__ import annotations

from collections import Counter


def detect_recurring_patterns(entries: list[dict], *, min_count: int = 3) -> list[dict]:
    if not entries:
        return []
    titles = Counter(str(e.get("title", "")).strip() for e in entries if e.get("title"))
    patterns = []
    for title, count in titles.most_common(10):
        if count >= min_count:
            patterns.append({"pattern": title, "count": count, "kind": "title_recurrence"})
    types = Counter(str(e.get("memory_type", "")) for e in entries)
    for mtype, count in types.most_common():
        if count >= min_count:
            patterns.append({"pattern": mtype, "count": count, "kind": "type_recurrence"})
    return patterns
