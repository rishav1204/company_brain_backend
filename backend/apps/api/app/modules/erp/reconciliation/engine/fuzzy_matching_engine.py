from __future__ import annotations

import re
from difflib import SequenceMatcher


def tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"[\s,/\-_.]+", (text or "").lower()) if len(t) > 2}


def narration_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_l, b_l = a.lower().strip(), b.lower().strip()
    if a_l in b_l or b_l in a_l:
        return 1.0
    tokens_a, tokens_b = tokenize(a_l), tokenize(b_l)
    if not tokens_a or not tokens_b:
        return SequenceMatcher(None, a_l, b_l).ratio()
    overlap = len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)
    seq = SequenceMatcher(None, a_l, b_l).ratio()
    return round(min(1.0, overlap * 0.6 + seq * 0.4), 4)


def counterparty_fuzzy(bank_narration: str, counterparty_name: str) -> float:
    return narration_similarity(bank_narration, counterparty_name)
