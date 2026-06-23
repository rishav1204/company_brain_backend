"""Typed domain errors for ERP posting and financial operations."""
from __future__ import annotations


class FinanceDomainError(Exception):
    """Base class for finance domain failures."""


class PostingError(FinanceDomainError):
    pass


class InvoiceError(FinanceDomainError):
    pass


class TreasuryError(FinanceDomainError):
    pass
