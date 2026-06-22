from dataclasses import dataclass

from app.core.config import settings


@dataclass
class ChunkConfig:
    chunk_size_tokens: int = settings.retrieval_chunk_size_tokens
    overlap_ratio: float = settings.retrieval_chunk_overlap_ratio


def chunk_text(text: str, config: ChunkConfig | None = None) -> list[str]:
    if config is None:
        config = ChunkConfig()
    words = text.split()
    if not words:
        return []

    size = max(50, config.chunk_size_tokens)
    overlap = int(size * max(0.0, min(config.overlap_ratio, 0.5)))
    stride = max(1, size - overlap)
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + size)
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += stride
    return chunks


def extract_metadata(text: str) -> dict:
    lowered = text.lower()
    return {
        "priority": "high" if "urgent" in lowered else "normal",
        "risk": "high" if "risk" in lowered or "blocked" in lowered else "medium",
        "contains_amount": "$" in text,
    }
