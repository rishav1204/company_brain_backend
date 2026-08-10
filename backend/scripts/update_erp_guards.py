"""One-off script to align ERP guards with DB-backed permission checks."""
from __future__ import annotations

import pathlib
import re

UPDATES = {
    "procurement/security/procurement_guard.py": ("procurement", ["erp.procurement.admin", "procurement.admin"], "Procurement admin required"),
    "inventory/security/inventory_guard.py": ("inventory", ["erp.inventory.admin", "inventory.admin"], "Inventory admin required"),
    "tax/security/tax_guard.py": ("tax", ["erp.tax.admin", "gst.admin", "tds.admin"], "Tax admin required"),
    "treasury/security/treasury_guard.py": ("treasury", ["erp.treasury.admin", "treasury.admin"], "Treasury admin required"),
    "banking/security/banking_guard.py": ("banking", ["erp.banking.admin", "banking.admin"], "Banking admin required"),
    "reconciliation/security/reconciliation_guard.py": ("reconciliation", ["erp.reconciliation.admin", "reconciliation.admin"], "Reconciliation admin required"),
    "coa/security/coa_guard.py": ("coa", ["erp.coa.admin", "coa.admin"], "COA admin required"),
    "vouchers/security/voucher_guard.py": ("vouchers", ["erp.voucher.admin", "voucher.admin"], "Voucher admin required"),
    "fiscal/security/fiscal_guard.py": ("fiscal", ["erp.fiscal.admin", "fiscal.admin", "period.close"], "Fiscal admin required"),
    "assets/security/asset_guard.py": ("assets", ["erp.assets.admin", "assets.admin"], "Assets admin required"),
    "expenses/security/expense_guard.py": ("expenses", ["erp.expense.admin", "expense.admin"], "Expense admin required"),
    "compliance/security/compliance_guard.py": ("compliance", ["erp.compliance.admin", "compliance.admin"], "Compliance admin required"),
    "consolidation/security/consolidation_guard.py": ("consolidation", ["erp.consolidation.admin", "consolidation.admin"], "Consolidation admin required"),
    "reporting/security/reporting_guard.py": ("reporting", ["erp.reporting.admin", "reporting.admin"], "Reporting admin required"),
}

base = pathlib.Path(__file__).resolve().parents[1] / "apps" / "api" / "app" / "modules" / "erp"
for rel, (billing, perms, detail) in UPDATES.items():
    path = base / rel
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    funcs = re.findall(r"^def (require_\w+)", text, re.M)
    fname = funcs[0] if funcs else f"require_{billing}_admin"
    content = f'''from __future__ import annotations

from fastapi import Depends

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.erp.security.access_guard import require_erp_mutation_access
from app.modules.platform.billing.security.billing_enforce import enforce_billing


def {fname}(context: RequestContext = Depends(build_request_context)) -> RequestContext:
    enforce_billing(context.org_id, "{billing}")
    require_erp_mutation_access(
        context,
        permission_keys={perms!r},
        detail="{detail}",
    )
    return context
'''
    path.write_text(content, encoding="utf-8")
    print("updated", path)
