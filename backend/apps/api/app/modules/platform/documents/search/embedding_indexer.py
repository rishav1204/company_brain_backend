from __future__ import annotations

from app.services.llm_provider import llm_provider


def make_embedding(text: str) -> list[float]:
    if llm_provider.is_ready():
        return llm_provider.generate_embedding(org_id="system", text=text)
    return [0.0] * 1536
