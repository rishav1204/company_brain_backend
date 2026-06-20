from __future__ import annotations

from app.services import llm_provider


def embed_text(org_id: str, text: str) -> list[float]:
    cleaned = (text or "").strip()
    if not cleaned:
        return [0.0] * 1536
    try:
        return llm_provider.generate_embedding(org_id=org_id, text=cleaned[:8000])
    except Exception:
        return _hash_fallback_embedding(cleaned)


def _hash_fallback_embedding(text: str) -> list[float]:
    """Deterministic pseudo-embedding for offline/tests when LLM unavailable."""
    import hashlib

    digest = hashlib.sha256(text.encode()).digest()
    vec = []
    for i in range(1536):
        byte = digest[i % len(digest)]
        vec.append((byte / 255.0) * 2 - 1)
    return vec
