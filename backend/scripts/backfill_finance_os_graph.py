"""Backfill Finance OS graph from historical ERP data."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.modules.finance_os.graph.services.graph_projection_service import rebuild_org


def backfill_org(org_id: str) -> dict:
    result = rebuild_org(org_id)
    return {"org_id": org_id, "rebuild": result}


if __name__ == "__main__":
    target = os.environ.get("ORG_ID", "")
    if not target:
        print("Set ORG_ID env var")
        sys.exit(1)
    print(backfill_org(target))
