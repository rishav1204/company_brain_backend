from __future__ import annotations

import re

GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


def validate_gstin(gstin: str | None) -> str | None:
    if not gstin:
        return None
    normalized = str(gstin).strip().upper()
    if not GSTIN_PATTERN.match(normalized):
        raise ValueError(f"Invalid GSTIN format: {gstin}")
    return normalized


def validate_pan(pan: str | None) -> str | None:
    if not pan:
        return None
    normalized = str(pan).strip().upper()
    if not PAN_PATTERN.match(normalized):
        raise ValueError(f"Invalid PAN format: {pan}")
    return normalized


def state_from_gstin(gstin: str | None) -> str | None:
    if not gstin or len(gstin) < 2:
        return None
    return str(gstin)[:2]
