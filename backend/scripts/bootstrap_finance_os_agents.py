#!/usr/bin/env python3
"""Bootstrap Finance OS agent module metadata for an org (no ERP mutations)."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_ROOT = os.path.join(ROOT, "apps", "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)


def bootstrap_org(org_id: str) -> dict:
    from app.modules.finance_os.agents.orchestrator.agent_registry import AGENT_CATALOG
    from app.modules.finance_os.agents.repositories.execution_repository import execution_repository

    return {
        "org_id": org_id,
        "schema_ready": execution_repository.schema_ready(),
        "agents_registered": len(AGENT_CATALOG),
        "agent_names": [a["agent_name"] for a in AGENT_CATALOG],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Finance OS agents for an org")
    parser.add_argument("--org-id", required=True)
    args = parser.parse_args()
    result = bootstrap_org(args.org_id)
    print(result)


if __name__ == "__main__":
    main()
