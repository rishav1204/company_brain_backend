from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.tools.tool_spec import ToolSpec


def _r(tool: str, method: str, module: str, service: str, fn: str, **kw) -> ToolSpec:
    return ToolSpec(
        tool=tool,
        method=method,
        module=module,
        service=service,
        fn=fn,
        read_only=True,
        policy_action=kw.pop("policy_action", f"{tool}.{method}"),
        **kw,
    )


READ_SPECS: list[ToolSpec] = [
    # Procurement
    _r("procurement", "list_pos", "app.modules.erp.procurement.repositories.po_repository", "po_repository", "list", defaults={"limit": 50}),
    _r("procurement", "get_po", "app.modules.erp.procurement.repositories.po_repository", "po_repository", "get", required=("po_id",)),
    _r("procurement", "list_requisitions", "app.modules.erp.procurement.services.requisition_service", "requisition_service", "list"),
    _r("procurement", "get_requisition", "app.modules.erp.procurement.services.requisition_service", "requisition_service", "get", required=("pr_id",)),
    _r("procurement", "list_grns", "app.modules.erp.procurement.services.grn_service", "grn_service", "list_for_po", required=("po_id",)),
    _r("procurement", "list_matches", "app.modules.erp.procurement.services.matching_service", "matching_service", "list_matches"),
    _r("procurement", "get_match_for_invoice", "app.modules.erp.procurement.services.matching_service", "matching_service", "get_for_invoice", required=("invoice_id",)),
    _r("procurement", "list_policies", "app.modules.erp.procurement.services.procurement_policy_service", "procurement_policy_service", "list_policies"),
    # Inventory
    _r("inventory", "list_balances", "app.modules.erp.inventory.services.inventory_service", "inventory_service", "list_balances", defaults={"limit": 100}),
    _r("inventory", "get_balance", "app.modules.erp.inventory.services.inventory_service", "inventory_service", "get_balance", required=("item_id", "warehouse_id")),
    _r("inventory", "list_items", "app.modules.erp.inventory.services.item_service", "item_service", "list"),
    _r("inventory", "get_item", "app.modules.erp.inventory.services.item_service", "item_service", "get", required=("item_id",)),
    _r("inventory", "list_warehouses", "app.modules.erp.inventory.services.warehouse_service", "warehouse_service", "list"),
    _r("inventory", "list_movements", "app.modules.erp.inventory.services.movement_service", "movement_service", "list_movements"),
    _r("inventory", "validate_close", "app.modules.erp.inventory.services.inventory_close_service", "inventory_close_service", "validate_period_close"),
    _r("inventory", "list_valuation_snapshots", "app.modules.erp.inventory.services.valuation_service", "valuation_service", "list_snapshots"),
    # AP
    _r("ap", "list_invoices", "app.modules.erp.accounts_payable.services.invoice_service", "invoice_service", "list_invoices"),
    _r("ap", "get_invoice", "app.modules.erp.accounts_payable.services.invoice_service", "invoice_service", "get_invoice", required=("invoice_id",)),
    _r("ap", "list_vendors", "app.modules.erp.accounts_payable.services.vendor_service", "vendor_service", "list_vendors"),
    _r("ap", "get_vendor", "app.modules.erp.accounts_payable.services.vendor_service", "vendor_service", "get_vendor", required=("vendor_id",)),
    _r("ap", "list_outstanding", "app.modules.erp.accounts_payable.repositories.invoice_repository", "invoice_repository", "list_outstanding"),
    _r("ap", "list_payments", "app.modules.erp.accounts_payable.services.payment_service", "payment_service", "list_payments"),
    _r("ap", "aging_report", "app.modules.erp.accounts_payable.services.aging_service", "aging_service", "report"),
    _r("ap", "vendor_balances", "app.modules.erp.accounts_payable.services.vendor_balance_service", "vendor_balance_service", "list_balances"),
    _r("ap", "check_duplicate", "app.modules.erp.accounts_payable.services.duplicate_invoice_service", "duplicate_invoice_service", "check_duplicate"),
    _r("ap", "propose_payment_schedule", "app.modules.erp.accounts_payable.services.payment_scheduler_service", "payment_scheduler_service", "propose_schedule"),
    # AR
    _r("ar", "list_invoices", "app.modules.erp.accounts_receivable.services.sales_invoice_service", "sales_invoice_service", "list_invoices"),
    _r("ar", "get_invoice", "app.modules.erp.accounts_receivable.services.sales_invoice_service", "sales_invoice_service", "get_invoice", required=("invoice_id",)),
    _r("ar", "list_customers", "app.modules.erp.accounts_receivable.services.customer_service", "customer_service", "list_customers"),
    _r("ar", "get_customer", "app.modules.erp.accounts_receivable.services.customer_service", "customer_service", "get_customer", required=("customer_id",)),
    _r("ar", "list_overdue", "app.modules.erp.accounts_receivable.repositories.invoice_repository", "ar_invoice_repository", "list_overdue"),
    _r("ar", "list_outstanding", "app.modules.erp.accounts_receivable.repositories.invoice_repository", "ar_invoice_repository", "list_outstanding"),
    _r("ar", "aging_report", "app.modules.erp.accounts_receivable.services.aging_service", "aging_service", "report"),
    _r("ar", "list_receipts", "app.modules.erp.accounts_receivable.services.collection_service", "collection_service", "list_receipts"),
    _r("ar", "customer_balances", "app.modules.erp.accounts_receivable.services.customer_balance_service", "customer_balance_service", "list_balances"),
    _r("ar", "collection_forecast", "app.modules.erp.accounts_receivable.services.ai_collection_service", "ai_collection_service", "forecast"),
    # GL
    _r("gl", "list_entries", "app.modules.erp.gl.services.ledger_service", "ledger_service", "list_entries"),
    _r("gl", "list_balances", "app.modules.erp.gl.services.balance_service", "balance_service", "list_by_period"),
    _r("gl", "trial_balance", "app.modules.erp.gl.services.trial_balance_service", "trial_balance_service", "generate"),
    _r("gl", "list_periods", "app.modules.erp.gl.services.fiscal_period_service", "fiscal_period_service", "list"),
    # COA
    _r("coa", "list_accounts", "app.modules.erp.coa.services.account_service", "account_service", "list"),
    _r("coa", "get_account", "app.modules.erp.coa.repositories.account_repository", "account_repository", "get", required=("account_id",)),
    _r("coa", "list_groups", "app.modules.erp.coa.services.account_group_service", "account_group_service", "list"),
    _r("coa", "list_cost_centers", "app.modules.erp.coa.services.cost_center_service", "cost_center_service", "list"),
    _r("coa", "list_financial_mappings", "app.modules.erp.coa.services.mapping_service", "mapping_service", "list_financial_mappings"),
    _r("coa", "list_gst_mappings", "app.modules.erp.coa.services.mapping_service", "mapping_service", "list_gst_mappings"),
    # Journals (tool name avoids forbidden "journal")
    _r("journals", "list", "app.modules.erp.journals.services.journal_service", "journal_service", "list"),
    _r("journals", "get", "app.modules.erp.journals.services.journal_service", "journal_service", "get", required=("journal_id",)),
    _r("journals", "list_approval_queue", "app.modules.erp.journals.services.approval_service", "approval_service", "list_approval_queue"),
    _r("journals", "list_recurring", "app.modules.erp.journals.services.recurring_journal_service", "recurring_journal_service", "list_templates"),
    _r("journals", "list_accruals", "app.modules.erp.journals.services.accrual_service", "accrual_service", "list_accruals"),
    # Vouchers
    _r("vouchers", "list", "app.modules.erp.vouchers.services.voucher_service", "voucher_service", "list"),
    _r("vouchers", "get", "app.modules.erp.vouchers.services.voucher_service", "voucher_service", "get", required=("voucher_id",)),
    # Banking
    _r("banking", "list_accounts", "app.modules.erp.banking.services.bank_account_service", "bank_account_service", "list_accounts"),
    _r("banking", "get_account", "app.modules.erp.banking.services.bank_account_service", "bank_account_service", "get_account", required=("account_id",)),
    _r("banking", "list_transactions", "app.modules.erp.banking.services.transaction_service", "transaction_service", "list_transactions"),
    _r("banking", "list_payment_requests", "app.modules.erp.banking.services.payment_execution_service", "payment_execution_service", "list_requests"),
    _r("banking", "list_beneficiaries", "app.modules.erp.banking.services.beneficiary_service", "beneficiary_service", "list"),
    # Treasury
    _r("treasury", "get_cash_position", "app.modules.erp.treasury.services.cash_position_service", "cash_position_service", "snapshot_all"),
    _r("treasury", "snapshot_account", "app.modules.erp.treasury.services.cash_position_service", "cash_position_service", "snapshot_account", required=("bank_account_id",)),
    _r("treasury", "list_alerts", "app.modules.erp.treasury.services.liquidity_service", "liquidity_service", "list_alerts"),
    _r("treasury", "build_forecast", "app.modules.erp.treasury.services.treasury_forecast_service", "treasury_forecast_service", "build_forecast"),
    _r("treasury", "list_transfers", "app.modules.erp.treasury.services.transfer_service", "transfer_service", "list"),
    _r("treasury", "liquidity_analyze", "app.modules.erp.treasury.services.liquidity_service", "liquidity_service", "analyze"),
    _r("treasury", "cashflow_forecast", "app.modules.erp.treasury.services.cashflow_service", "cashflow_service", "build_forecast"),
    # Reconciliation
    _r("reconciliation", "list_exceptions", "app.modules.erp.reconciliation.services.exception_service", "exception_service", "list"),
    _r("reconciliation", "list", "app.modules.erp.reconciliation.repositories.reconciliation_repository", "reconciliation_repository", "list"),
    _r("reconciliation", "suggest_matches", "app.modules.erp.reconciliation.services.reconciliation_service", "reconciliation_service", "suggest_matches"),
    _r("reconciliation", "list_suggestions", "app.modules.erp.reconciliation.services.reconciliation_service", "reconciliation_service", "list_suggestions"),
    _r("reconciliation", "list_workbench", "app.modules.erp.reconciliation.services.bank_match_service", "bank_match_service", "list_workbench"),
    # Fiscal
    _r("fiscal", "list_years", "app.modules.erp.fiscal.services.fiscal_year_service", "fiscal_year_service", "list_fiscal_years"),
    _r("fiscal", "list_periods", "app.modules.erp.fiscal.services.fiscal_period_service", "fiscal_period_service", "list"),
    _r("fiscal", "close_checklist", "app.modules.erp.fiscal.services.close_service", "close_service", "list_checklist"),
    _r("fiscal", "validate_period", "app.modules.erp.fiscal.services.posting_validation_service", "posting_validation_service", "validate_period"),
    # Tax / GST (tool name avoids forbidden "gst")
    _r("tax_gst", "list_registrations", "app.modules.erp.tax.services.gst_service", "gst_service", "list_registrations"),
    _r("tax_gst", "list_returns", "app.modules.erp.tax.services.gst_return_service", "gst_return_service", "list_returns"),
    _r("tax_gst", "get_return", "app.modules.erp.tax.services.gst_return_service", "gst_return_service", "get_return", required=("return_id",)),
    _r("tax_gst", "list_transactions", "app.modules.erp.tax.repositories.gst_repository", "gst_transaction_repository", "list"),
    _r("tax_gst", "list_reconciliations", "app.modules.erp.tax.services.gst_reconciliation_service", "gst_reconciliation_service", "list_reconciliations"),
    _r("tax_gst", "calculate", "app.modules.erp.tax.services.gst_calculation_service", "gst_calculation_service", "calculate"),
    _r("tax_tds", "list_sections", "app.modules.erp.tax.services.tds_service", "tds_service", "list_sections"),
    _r("tax_tds", "list_transactions", "app.modules.erp.tax.services.tds_service", "tds_service", "list_transactions"),
    _r("tax_tds", "list_returns", "app.modules.erp.tax.services.tds_return_service", "tds_return_service", "list_returns"),
    _r("tax_tds", "list_challans", "app.modules.erp.tax.services.tds_challan_service", "tds_challan_service", "list_challans"),
    _r("tax_compliance", "list_obligations", "app.modules.erp.tax.services.compliance_calendar_service", "compliance_calendar_service", "list_obligations"),
    _r("tax_compliance", "check_upcoming", "app.modules.erp.tax.services.compliance_calendar_service", "compliance_calendar_service", "check_upcoming"),
    # Expenses
    _r("expenses", "list_claims", "app.modules.erp.expenses.services.claim_service", "claim_service", "list"),
    _r("expenses", "get_claim", "app.modules.erp.expenses.services.claim_service", "claim_service", "get", required=("claim_id",)),
    _r("expenses", "list_policies", "app.modules.erp.expenses.services.policy_service", "expense_policy_service", "list_policies"),
    _r("expenses", "list_open_advances", "app.modules.erp.expenses.services.advance_service", "advance_service", "list_open"),
    # Assets
    _r("assets", "list", "app.modules.erp.assets.services.asset_service", "asset_service", "list"),
    _r("assets", "get", "app.modules.erp.assets.services.asset_service", "asset_service", "get", required=("asset_id",)),
    _r("assets", "list_categories", "app.modules.erp.assets.repositories.category_repository", "category_repository", "list_active"),
    _r("assets", "list_candidates", "app.modules.erp.assets.services.candidate_service", "candidate_service", "list"),
    _r("assets", "get_register", "app.modules.erp.assets.services.asset_register_service", "asset_register_service", "get_register", required=("asset_id",)),
    # Reporting
    _r("reporting", "pnl", "app.modules.erp.reporting.services.pnl_service", "pnl_service", "get"),
    _r("reporting", "balance_sheet", "app.modules.erp.reporting.services.balance_sheet_service", "balance_sheet_service", "get"),
    _r("reporting", "cash_flow", "app.modules.erp.reporting.services.cash_flow_service", "cash_flow_service", "get"),
    _r("reporting", "ap_aging", "app.modules.erp.reporting.services.aging_report_service", "aging_report_service", "get_ap"),
    _r("reporting", "ar_aging", "app.modules.erp.reporting.services.aging_report_service", "aging_report_service", "get_ar"),
    _r("reporting", "gst_report", "app.modules.erp.reporting.services.gst_report_service", "gst_report_service", "get"),
    _r("reporting", "tds_report", "app.modules.erp.reporting.services.tds_report_service", "tds_report_service", "get"),
    _r("reporting", "treasury_report", "app.modules.erp.reporting.services.treasury_report_service", "treasury_report_service", "cash_position"),
    # Compliance (M21)
    _r("compliance", "list_obligations", "app.modules.erp.compliance.services.obligation_service", "obligation_service", "list"),
    _r("compliance", "upcoming", "app.modules.erp.compliance.services.obligation_service", "obligation_service", "upcoming"),
    _r("compliance", "calendar", "app.modules.erp.compliance.services.calendar_service", "calendar_service", "list"),
    _r("compliance", "dashboard", "app.modules.erp.compliance.services.compliance_dashboard_service", "compliance_dashboard_service", "build"),
    # Consolidation
    _r("consolidation", "list_runs", "app.modules.erp.consolidation.services.consolidation_service", "consolidation_service", "list_runs"),
    _r("consolidation", "list_hierarchy", "app.modules.erp.consolidation.services.entity_service", "entity_service", "list_hierarchy"),
    _r("consolidation", "list_intercompany", "app.modules.erp.consolidation.services.intercompany_service", "intercompany_service", "list_transactions"),
    _r("consolidation", "list_branches", "app.modules.erp.consolidation.services.branch_service", "branch_service", "list_all"),
    # Finance OS intelligence (read)
    _r("invoice_ai", "list_predictions", "app.modules.finance_os.invoice_ai.services.prediction_service", "prediction_service", "list_suggestions", required=("extraction_id",)),
    _r("analytics", "list_kpis", "app.modules.finance_os.analytics.services.kpi_service", "kpi_service", "list"),
    _r("analytics", "executive_dashboard", "app.modules.finance_os.analytics.services.executive_dashboard_service", "executive_dashboard_service", "get"),
    _r("analytics", "list_insights", "app.modules.finance_os.analytics.services.insight_service", "insight_service", "list"),
    _r("forecasting", "list_forecasts", "app.modules.finance_os.forecasting.repositories.forecast_repository", "forecast_repository", "list_latest"),
    _r("workflow_intel", "list_bottlenecks", "app.modules.finance_os.workflow_intelligence.services.bottleneck_service", "bottleneck_service", "list_bottlenecks"),
    _r("workflow_intel", "list_sla_risks", "app.modules.finance_os.workflow_intelligence.services.sla_prediction_service", "sla_prediction_service", "list_risks"),
    _r("audit", "search_timeline", "app.modules.finance_os.audit_explorer.repositories.timeline_repository", "timeline_repository", "search"),
]
