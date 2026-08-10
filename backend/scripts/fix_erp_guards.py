"""Restore ERP guards with read + mutation helpers after security hardening."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "apps" / "api" / "app" / "modules" / "erp"

HEADER = '''from __future__ import annotations

from fastapi import Depends

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.erp.security.access_guard import require_erp_mutation_access, require_erp_read_access
from app.modules.platform.billing.security.billing_enforce import enforce_billing

'''

GUARDS = {
    "tax/security/tax_guard.py": [
        ("require_tax_admin", "tax", "mutation", ["erp.tax.admin", "gst.admin", "tds.admin"], "Tax admin required"),
        ("require_tax_read", "tax", "read", ["erp.tax.admin", "gst.read", "tds.read", "gst.admin"], "Tax read required"),
    ],
    "banking/security/banking_guard.py": [
        ("require_banking_admin", "banking", "mutation", ["erp.banking.admin", "banking.admin"], "Banking admin required"),
        ("require_banking_read", "banking", "read", ["erp.banking.admin", "banking.read", "banking.admin"], "Banking read required"),
    ],
    "procurement/security/procurement_guard.py": [
        ("require_procurement_admin", "procurement", "mutation", ["erp.procurement.admin", "procurement.admin"], "Procurement admin required"),
        ("require_procurement_read", "procurement", "read", ["erp.procurement.admin", "procurement.read", "procurement.admin"], "Procurement read required"),
        ("require_procurement_receive", "procurement", "mutation", ["erp.procurement.receive", "procurement.admin", "erp.procurement.admin"], "Procurement receive required"),
    ],
    "fiscal/security/fiscal_guard.py": [
        ("require_fiscal_admin", "fiscal", "mutation", ["erp.fiscal.admin", "fiscal.admin", "period.close"], "Fiscal admin required"),
        ("require_fiscal_read", "fiscal", "read", ["erp.fiscal.admin", "fiscal.read", "fiscal.admin"], "Fiscal read required"),
    ],
    "compliance/security/compliance_guard.py": [
        ("require_compliance_admin", "compliance", "mutation", ["erp.compliance.admin", "compliance.admin"], "Compliance admin required"),
        ("require_compliance_read", "compliance", "read", ["erp.compliance.admin", "compliance.read"], "Compliance read required"),
    ],
    "consolidation/security/consolidation_guard.py": [
        ("require_consolidation_admin", "consolidation", "mutation", ["erp.consolidation.admin", "consolidation.admin"], "Consolidation admin required"),
        ("require_consolidation_read", "consolidation", "read", ["erp.consolidation.admin", "consolidation.read"], "Consolidation read required"),
    ],
    "reporting/security/reporting_guard.py": [
        ("require_reporting_export", "reporting", "mutation", ["erp.reporting.export", "erp.reporting.admin", "reporting.admin"], "Reporting export required"),
        ("require_reporting_read", "reporting", "read", ["erp.reporting.admin", "reporting.read", "reporting.admin"], "Reporting read required"),
    ],
    "expenses/security/expense_guard.py": [
        ("require_expense_create", "expenses", "mutation", ["erp.expense.create", "erp.expense.admin", "expense.admin"], "Expense create required"),
        ("require_expense_reimburse", "expenses", "mutation", ["erp.expense.reimburse", "erp.expense.admin"], "Expense reimburse required"),
        ("require_expense_read", "expenses", "read", ["erp.expense.admin", "expense.read", "expense.admin"], "Expense read required"),
    ],
    "assets/security/asset_guard.py": [
        ("require_asset_create", "assets", "mutation", ["erp.assets.create", "erp.assets.admin", "assets.admin"], "Asset create required"),
        ("require_asset_depreciate", "assets", "mutation", ["erp.assets.depreciate", "erp.assets.admin"], "Asset depreciate required"),
        ("require_asset_read", "assets", "read", ["erp.assets.admin", "assets.read", "assets.admin"], "Asset read required"),
    ],
    "vouchers/security/voucher_guard.py": [
        ("require_voucher_admin", "vouchers", "mutation", ["erp.voucher.admin", "voucher.admin", "voucher.approve"], "Voucher admin required"),
        ("require_voucher_read", "vouchers", "read", ["erp.voucher.admin", "voucher.read", "voucher.admin"], "Voucher read required"),
    ],
    "inventory/security/inventory_guard.py": [
        ("require_inventory_create", "inventory", "mutation", ["erp.inventory.create", "erp.inventory.admin", "inventory.admin"], "Inventory create required"),
        ("require_inventory_issue", "inventory", "mutation", ["erp.inventory.issue", "erp.inventory.admin"], "Inventory issue required"),
        ("require_inventory_adjust", "inventory", "mutation", ["erp.inventory.adjust", "erp.inventory.admin"], "Inventory adjust required"),
        ("require_inventory_transfer", "inventory", "mutation", ["erp.inventory.transfer", "erp.inventory.admin"], "Inventory transfer required"),
        ("require_inventory_read", "inventory", "read", ["erp.inventory.admin", "inventory.read", "inventory.admin"], "Inventory read required"),
    ],
    "reconciliation/security/reconciliation_guard.py": [
        ("require_reconciliation_admin", "reconciliation", "mutation", ["erp.reconciliation.admin", "reconciliation.admin"], "Reconciliation admin required"),
        ("require_reconciliation_read", "reconciliation", "read", ["erp.reconciliation.admin", "reconciliation.read"], "Reconciliation read required"),
    ],
    "treasury/security/treasury_guard.py": [
        ("require_treasury_admin", "treasury", "mutation", ["erp.treasury.admin", "treasury.admin"], "Treasury admin required"),
        ("require_treasury_read", "treasury", "read", ["erp.treasury.admin", "treasury.read", "treasury.admin"], "Treasury read required"),
    ],
}


def _fn(name, billing, mode, perms, detail):
    helper = "require_erp_mutation_access" if mode == "mutation" else "require_erp_read_access"
    return f'''
def {name}(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "{billing}")
    {helper}(
        context,
        permission_keys={perms!r},
        detail="{detail}",
    )
    return context
'''


for rel, fns in GUARDS.items():
    path = ROOT / rel
    body = HEADER + "".join(_fn(*f) for f in fns)
    path.write_text(body, encoding="utf-8")
    print("fixed", path)
