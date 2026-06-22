#!/usr/bin/env python3
"""Bootstrap M34 governance policies and approval matrix for an org."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.modules.platform.governance.policies import ALL_SEED_POLICIES
from app.modules.platform.governance.services.policy_service import governance_policy_service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", required=True)
    args = parser.parse_args()
    count = 0
    for p in ALL_SEED_POLICIES:
        governance_policy_service.upsert_policy(
            args.org_id,
            policy_key=p["policy_code"],
            policy_type=p["policy_type"],
            conditions=p.get("conditions") or {},
            actions=p.get("actions") or {},
        )
        count += 1
    print({"status": "ok", "policies_upserted": count})


if __name__ == "__main__":
    main()
