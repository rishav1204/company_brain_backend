"""ERP domain event consumers (re-exported from platform.events.consumers.handlers)."""
from app.modules.platform.events.consumers.handlers.legacy_handlers import (
    _consume_ar_events as consume_ar_events,
    _consume_asset_events as consume_asset_events,
    _consume_coa_events as consume_coa_events,
    _consume_expense_events as consume_expense_events,
    _consume_fiscal_events as consume_fiscal_events,
    _consume_inventory_events as consume_inventory_events,
    _consume_journal_events as consume_journal_events,
    _consume_procurement_events as consume_procurement_events,
    _consume_tax_events as consume_tax_events,
    _consume_treasury_events as consume_treasury_events,
)

__all__ = [
    "consume_ar_events",
    "consume_asset_events",
    "consume_coa_events",
    "consume_expense_events",
    "consume_fiscal_events",
    "consume_inventory_events",
    "consume_journal_events",
    "consume_procurement_events",
    "consume_tax_events",
    "consume_treasury_events",
]
