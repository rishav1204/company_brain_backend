#!/usr/bin/env python3
"""Bootstrap M35 sample holding company hierarchy for an org."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.modules.core.iam.repositories import organization_repo
from app.modules.erp.consolidation.services.entity_service import entity_service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", required=True)
    args = parser.parse_args()
    org_id = args.org_id

    companies = organization_repo.list_companies(org_id)
    if len(companies) < 3:
        organization_repo.create_company(org_id, legal_name="Holding Company", gstin="29HOLD0000H1Z5")
        organization_repo.create_company(org_id, legal_name="Subsidiary A")
        organization_repo.create_company(org_id, legal_name="Subsidiary B")
        companies = organization_repo.list_companies(org_id)

    holding_id = str(companies[0]["id"])
    sub_a = str(companies[1]["id"])
    sub_b = str(companies[2]["id"])

    entity_service.link_entities(org_id, parent_company_id=holding_id, child_company_id=sub_a, ownership_percent=100.0)
    entity_service.link_entities(org_id, parent_company_id=holding_id, child_company_id=sub_b, ownership_percent=80.0)
    print({"status": "ok", "holding_company_id": holding_id, "subsidiaries": [sub_a, sub_b]})


if __name__ == "__main__":
    main()
