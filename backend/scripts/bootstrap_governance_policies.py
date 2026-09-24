#!/usr/bin/env python3
"""Bootstrap M34 governance policies and approval matrix for an org.

Seed templates in policies/*.py are NOT runtime authority. Amount thresholds
prefer platform.regulatory_param (governance.*) when the catalog is present.
"""

from __future__ import annotations

import argparse
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.modules.platform.governance.policies import ALL_SEED_POLICIES
from app.modules.platform.governance.services.policy_service import governance_policy_service

# Map policy_code → regulatory param_key used to fill conditions.amount_gt
_AMOUNT_PARAM_BY_POLICY = {
    "AP_INVOICE_APPROVAL_001": "governance.ap_invoice_approve_amount_gt",
    "JOURNAL_MANUAL_001": "governance.journal_post_amount_gt",
    "TREASURY_TRANSFER_001": "governance.treasury_transfer_amount_gt",
}


def _hydrate_amounts(policy: dict) -> dict:
    out = copy.deepcopy(policy)
    key = _AMOUNT_PARAM_BY_POLICY.get(str(out.get("policy_code") or ""))
    if not key:
        return out
    try:
        from app.modules.platform.regulatory.services.regulatory_resolver import (
            regulatory_resolver,
        )

        amount = regulatory_resolver.resolve_param_numeric(key, required=False, default=None)
        if amount is not None and amount > 0:
            cond = dict(out.get("conditions") or {})
            if "amount_gt" in cond:
                cond["amount_gt"] = float(amount)
                out["conditions"] = cond
    except Exception:
        pass
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", required=True)
    args = parser.parse_args()
    count = 0
    for p in ALL_SEED_POLICIES:
        seeded = _hydrate_amounts(p)
        governance_policy_service.upsert_policy(
            args.org_id,
            policy_key=seeded["policy_code"],
            policy_type=seeded["policy_type"],
            conditions=seeded.get("conditions") or {},
            actions=seeded.get("actions") or {},
        )
        count += 1
    print({"status": "ok", "policies_upserted": count})


if __name__ == "__main__":
    main()
