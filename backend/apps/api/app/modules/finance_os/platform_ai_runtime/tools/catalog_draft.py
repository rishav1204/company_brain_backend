from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.tools.tool_spec import ToolSpec


def _d(tool: str, method: str, module: str, service: str, fn: str, **kw) -> ToolSpec:
    return ToolSpec(
        tool=tool,
        method=method,
        module=module,
        service=service,
        fn=fn,
        read_only=False,
        requires_approval=True,
        policy_action=kw.pop("policy_action", f"{tool}.{method}"),
        **kw,
    )


DRAFT_SPECS: list[ToolSpec] = [
    # Procurement
    _d("procurement", "create_requisition", "app.modules.erp.procurement.services.requisition_service", "requisition_service", "create", actor_kwarg="created_by", compensation="procurement.cancel_requisition"),
    _d("procurement", "submit_requisition", "app.modules.erp.procurement.services.requisition_service", "requisition_service", "submit", required=("pr_id",), actor_kwarg="actor_id"),
    _d("procurement", "cancel_requisition", "app.modules.erp.procurement.services.requisition_service", "requisition_service", "cancel", required=("pr_id",), actor_kwarg="actor_id"),
    _d("procurement", "create_po", "app.modules.erp.procurement.services.po_service", "po_service", "create", required=("vendor_id",), actor_kwarg="created_by", compensation="procurement.cancel_po"),
    _d("procurement", "submit_po", "app.modules.erp.procurement.services.po_service", "po_service", "submit_for_approval", required=("po_id",), actor_kwarg="actor_id"),
    _d("procurement", "create_grn", "app.modules.erp.procurement.services.grn_service", "grn_service", "create", required=("po_id",), actor_kwarg="received_by", compensation="procurement.cancel_grn"),
    _d("procurement", "cancel_po", "app.modules.erp.procurement.services.po_service", "po_service", "cancel", required=("po_id",), actor_kwarg="actor_id"),
    # confirm_grn + cancel_grn registered as custom handlers in erp_tools.py
    # Inventory
    _d("inventory", "create_item", "app.modules.erp.inventory.services.item_service", "item_service", "create", required=("item_name",), compensation="inventory.deactivate_item"),
    _d("inventory", "create_warehouse", "app.modules.erp.inventory.services.warehouse_service", "warehouse_service", "create", required=("warehouse_name",)),
    _d("inventory", "create_adjustment", "app.modules.erp.inventory.services.adjustment_service", "adjustment_service", "create", required=("item_id", "warehouse_id", "quantity")),
    # AP
    _d("ap", "create_invoice", "app.modules.erp.accounts_payable.services.invoice_service", "invoice_service", "create_invoice",
       required=("vendor_id", "invoice_number", "invoice_date", "invoice_amount", "gst_amount", "total_amount"),
       actor_kwarg="created_by", compensation="ap.cancel_invoice"),
    _d("ap", "submit_for_review", "app.modules.erp.accounts_payable.services.invoice_service", "invoice_service", "submit_for_review", required=("invoice_id",), actor_kwarg="actor_id"),
    _d("ap", "submit_for_approval", "app.modules.erp.accounts_payable.services.invoice_service", "invoice_service", "submit_for_approval", required=("invoice_id",), actor_kwarg="actor_id"),
    _d("ap", "create_vendor", "app.modules.erp.accounts_payable.services.vendor_service", "vendor_service", "create_vendor", required=("vendor_name",), actor_kwarg="created_by"),
    # AR
    _d("ar", "create_invoice", "app.modules.erp.accounts_receivable.services.sales_invoice_service", "sales_invoice_service", "create_invoice",
       required=("customer_id", "invoice_number", "invoice_date", "total_amount"), actor_kwarg="created_by"),
    _d("ar", "create_customer", "app.modules.erp.accounts_receivable.services.customer_service", "customer_service", "create_customer", required=("customer_name",), actor_kwarg="created_by"),
    # Journals (draft only — never post)
    _d("journals", "create_draft", "app.modules.erp.journals.services.journal_service", "journal_service", "create_draft",
       required=("journal_type", "posting_date"), actor_kwarg="created_by", compensation="journals.void_draft"),
    _d("journals", "submit_for_approval", "app.modules.erp.journals.services.approval_service", "approval_service", "submit_for_approval", required=("journal_id",), actor_kwarg="actor_id"),
    # Vouchers
    _d("vouchers", "create", "app.modules.erp.vouchers.services.voucher_service", "voucher_service", "create",
       required=("voucher_type", "voucher_date", "lines"), actor_kwarg="created_by", compensation="vouchers.cancel"),
    _d("vouchers", "submit_for_approval", "app.modules.erp.vouchers.services.voucher_service", "voucher_service", "submit_for_approval", required=("voucher_id",), actor_kwarg="submitted_by"),
    # Expenses
    _d("expenses", "create_claim", "app.modules.erp.expenses.services.claim_service", "claim_service", "create", actor_kwarg="created_by", compensation="expenses.cancel_claim"),
    _d("expenses", "submit_claim", "app.modules.erp.expenses.services.claim_service", "claim_service", "submit", required=("claim_id",), actor_kwarg="actor_id"),
    # Assets
    _d("assets", "create", "app.modules.erp.assets.services.asset_service", "asset_service", "create", required=("asset_name",), actor_kwarg="created_by", compensation="assets.dispose"),
    _d("assets", "submit", "app.modules.erp.assets.services.asset_service", "asset_service", "submit", required=("asset_id",), actor_kwarg="actor_id"),
    # Banking (request only — not execute)
    _d("banking", "create_payment_request", "app.modules.erp.banking.services.payment_execution_service", "payment_execution_service", "create_request",
       required=("payment_type", "beneficiary_type", "bank_account_id", "amount", "currency_code"), actor_kwarg="created_by"),
    # Treasury
    _d("treasury", "create_transfer", "app.modules.erp.treasury.services.transfer_service", "transfer_service", "create", required=("from_account_id", "to_account_id", "amount"), actor_kwarg="created_by"),
    # Fiscal
    _d("fiscal", "init_close", "app.modules.erp.fiscal.services.close_service", "close_service", "init_close", required=("period_id",)),
    _d("fiscal", "submit_close", "app.modules.erp.fiscal.services.close_service", "close_service", "submit_for_approval", required=("period_id",), actor_kwarg="started_by"),
    # Tax (generate/submit — not file)
    _d("tax_gst", "generate_return", "app.modules.erp.tax.services.gst_return_service", "gst_return_service", "generate_return", required=("return_period",), actor_kwarg="actor_id"),
    _d("tax_gst", "submit_return", "app.modules.erp.tax.services.gst_return_service", "gst_return_service", "submit_for_approval", required=("return_id",), actor_kwarg="actor_id"),
    _d("tax_tds", "generate_return", "app.modules.erp.tax.services.tds_return_service", "tds_return_service", "generate_return", required=("return_period",), actor_kwarg="actor_id"),
    # COA
    _d("coa", "create_account", "app.modules.erp.coa.services.account_service", "account_service", "create", required=("account_name", "account_code"), actor_kwarg="created_by"),
    # Workflow
    _d("workflow", "start", "app.modules.workflows.services.workflow_service", "workflow_service", "start_workflow",
       required=("workflow_key",), defaults={"entity_type": "workflow", "entity_id": ""}, actor_kwarg="user_id", org_style="kw"),
]
