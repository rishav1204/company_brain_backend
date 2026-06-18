from __future__ import annotations

import re

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


def validate_gstin(gstin: str | None) -> None:
    if not gstin:
        return
    if not GSTIN_RE.match(gstin.strip().upper()):
        raise ValueError(f"Invalid GSTIN format: {gstin}")


def validate_pan(pan: str | None) -> None:
    if not pan:
        return
    if not PAN_RE.match(pan.strip().upper()):
        raise ValueError(f"Invalid PAN format: {pan}")
