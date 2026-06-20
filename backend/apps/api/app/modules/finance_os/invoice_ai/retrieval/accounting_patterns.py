from __future__ import annotations

from app.modules.finance_os.invoice_ai.retrieval.vendor_memory import retrieve_vendor_patterns


def get_accounting_patterns(org_id: str, *, description: str, vendor_name: str) -> list[dict]:
    patterns = retrieve_vendor_patterns(org_id, vendor_name=vendor_name)
    if description:
        desc_patterns = retrieve_vendor_patterns(org_id, vendor_name=description[:80])
        seen = {p.get("content") for p in patterns}
        for p in desc_patterns:
            if p.get("content") not in seen:
                patterns.append(p)
    return patterns
