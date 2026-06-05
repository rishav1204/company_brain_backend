from __future__ import annotations

import re

GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


def validate_gstin(gstin: str | None) -> None:
    if not gstin:
        return
    normalized = str(gstin).strip().upper()
    if not GSTIN_PATTERN.match(normalized):
        raise ValueError(f"Invalid GSTIN format: {gstin}")


def validate_pan(pan: str | None) -> None:
    if not pan:
        return
    normalized = str(pan).strip().upper()
    if not PAN_PATTERN.match(normalized):
        raise ValueError(f"Invalid PAN format: {pan}")
