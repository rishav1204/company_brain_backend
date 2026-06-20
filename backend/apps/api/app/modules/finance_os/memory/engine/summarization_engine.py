from __future__ import annotations


def summarize_entries(entries: list[dict], *, max_chars: int = 500) -> str:
    if not entries:
        return ""
    titles = [str(e.get("title", "")).strip() for e in entries if e.get("title")]
    contents = [str(e.get("content", "")).strip() for e in entries if e.get("content")]
    if not contents:
        return ""
    unique_titles = list(dict.fromkeys(titles))[:5]
    sample = contents[:5]
    parts = []
    if unique_titles:
        parts.append("Topics: " + "; ".join(unique_titles))
    parts.append("Patterns: " + " | ".join(sample))
    summary = " ".join(parts)
    return summary[:max_chars]


def build_summary_title(memory_type: str, entity_type: str | None, count: int) -> str:
    label = memory_type.replace("_", " ").title()
    entity = (entity_type or "entity").replace("_", " ")
    return f"{label} summary ({count} memories for {entity})"
