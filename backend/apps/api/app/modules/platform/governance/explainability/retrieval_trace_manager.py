from __future__ import annotations

from typing import Any


def build_retrieval_trace(*, query: str, chunk_ids: list[str], scores: list[float]) -> dict[str, Any]:
    return {
        "query_hash": query[:64],
        "chunk_count": len(chunk_ids),
        "chunk_ids": chunk_ids[:20],
        "top_scores": scores[:10],
    }
