from __future__ import annotations

import re


def normalize_vendor_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r"\s+", " ", name.strip().upper())
    cleaned = re.sub(r"[^A-Z0-9 &.'-]", "", cleaned)
    return cleaned or None


def normalize_gstin(gstin: str | None) -> str | None:
    if not gstin:
        return None
    return gstin.strip().upper()
