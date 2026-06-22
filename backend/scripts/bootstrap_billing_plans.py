#!/usr/bin/env python3
"""Bootstrap M37 billing subscription and credit wallet for an org."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.modules.platform.billing.constants import DEFAULT_PLAN_KEY
from app.modules.platform.billing.services.subscription_service import subscription_service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--plan-key", default=DEFAULT_PLAN_KEY)
    args = parser.parse_args()
    sub = subscription_service.bootstrap_org(args.org_id, plan_key=args.plan_key)
    print({"status": "ok", "subscription": sub})


if __name__ == "__main__":
    main()
