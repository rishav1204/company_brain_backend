from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CanonicalVendor:
    name: str
    gstin: str | None = None
    email: str | None = None
    phone: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class CanonicalInvoice:
    invoice_number: str
    vendor: CanonicalVendor | None = None
    invoice_date: str | None = None  # ISO date string
    currency: str | None = None
    taxable_value: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    line_items: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class CanonicalPayment:
    payment_id: str
    amount: float
    currency: str | None = None
    paid_at: str | None = None
    vendor: CanonicalVendor | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class CanonicalJournal:
    journal_id: str
    posted_at: str | None = None
    entries: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class CanonicalBankTransaction:
    bank_tx_id: str
    amount: float
    currency: str | None = None
    occurred_at: str | None = None
    description: str | None = None
    reference: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class CanonicalGSTReturn:
    return_period: str  # e.g. "2026-04"
    status: str | None = None
    filed_at: str | None = None
    raw: dict[str, Any] | None = None

