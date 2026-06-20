"""Run M27 memory cleanup (delegates to finance_os.memory_cleanup_service)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.modules.finance_os.memory.services.memory_cleanup_service import apply_cleanup


if __name__ == "__main__":
    org_id = os.environ.get("ORG_ID", "")
    if not org_id:
        print("Set ORG_ID env var")
        sys.exit(1)
    print(apply_cleanup(org_id))
