"""Session-wide test setup.

Registers the ERP <-> Finance OS boundary (command registry, query registry,
intelligence ports) exactly like application startup in `app.main`, so module
tests that exercise ERP services get the same wiring as production.

Also provides the documentation-artifact fixtures used by the milestone
"drift" gates. Those artifacts live outside the package and are not always
present in a partial checkout, so the fixtures skip rather than fail when the
file is absent — a missing doc is not a broken build.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.modules.finance_os.bridges.erp_command_bridge.bootstrap import bootstrap_wave1_boundaries

bootstrap_wave1_boundaries()

REPO_ROOT = Path(__file__).resolve().parents[3]


def find_doc_artifact(*relative_parts: str) -> Path | None:
    """Locate a documentation artifact under docs/ (legacy backend/ path as fallback)."""
    for root in (REPO_ROOT / "docs", REPO_ROOT / "backend"):
        candidate = root.joinpath(*relative_parts)
        if candidate.is_file():
            return candidate
    return None


def require_doc_artifact(*relative_parts: str) -> Path:
    path = find_doc_artifact(*relative_parts)
    if path is None:
        pytest.skip(f"doc artifact not in this checkout: docs/{'/'.join(relative_parts)}")
    return path


@pytest.fixture(scope="session")
def erp_master_module_map() -> str:
    """Text of docs/ERP_MASTER_MODULE_MAP.md, the per-milestone status table."""
    return require_doc_artifact("ERP_MASTER_MODULE_MAP.md").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def completeness_audit_data() -> dict[str, Any]:
    """Parsed output of implementation_completeness_audit.py."""
    path = require_doc_artifact("ENTERPRISE_CODE_QUALITY_REVIEW_DATA.json")
    return json.loads(path.read_text(encoding="utf-8"))
