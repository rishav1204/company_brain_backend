from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeliveryResult:
    status: str
    provider: str
    detail: str | None = None
    response: dict | None = None
