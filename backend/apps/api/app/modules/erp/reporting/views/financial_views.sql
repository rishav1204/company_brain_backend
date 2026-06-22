-- Reference queries for M31 aggregation (batch only — not executed at request time)

-- Trial balance from ledger entries
-- SELECT account_id, SUM(debit_amount), SUM(credit_amount) FROM erp.ledger_entries GROUP BY account_id;

-- P&L rollups via COA mappings
-- SELECT m.reporting_category, SUM(ab.closing_balance)
-- FROM erp.financial_statement_mappings m
-- JOIN erp.account_balances ab ON ab.account_id = m.account_id
-- WHERE m.statement_type = 'profit_loss'
-- GROUP BY m.reporting_category;

-- Balance sheet rollups
-- WHERE m.statement_type = 'balance_sheet'
