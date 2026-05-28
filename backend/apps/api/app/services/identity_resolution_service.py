def canonicalize_key(raw_value: str) -> str:
    return raw_value.strip().lower().replace(" ", "_")


def resolve_identity(aliases: list[str], canonical_type: str = "entity") -> dict:
    normalized = [canonicalize_key(alias) for alias in aliases if alias.strip()]
    if not normalized:
        canonical_key = "unknown"
        confidence = 0.5
    else:
        frequency: dict[str, int] = {}
        for item in normalized:
            frequency[item] = frequency.get(item, 0) + 1
        canonical_key = sorted(frequency.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        confidence = 1.0 if len(set(normalized)) <= 1 else round(frequency[canonical_key] / len(normalized), 4)
    collisions = sorted([item for item in set(normalized) if item != canonical_key])
    return {
        "canonical_type": canonical_type,
        "canonical_key": canonical_key,
        "aliases": normalized,
        "confidence": confidence,
        "collisions": collisions,
    }
