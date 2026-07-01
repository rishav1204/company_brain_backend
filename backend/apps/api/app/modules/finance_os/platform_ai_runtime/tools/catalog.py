from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.tools.catalog_draft import DRAFT_SPECS
from app.modules.finance_os.platform_ai_runtime.tools.catalog_read import READ_SPECS
from app.modules.finance_os.platform_ai_runtime.tools.registry import ErpToolRegistry
from app.modules.finance_os.platform_ai_runtime.tools.tool_spec import register_specs

ALL_SPECS = READ_SPECS + DRAFT_SPECS


def register_catalog(registry: ErpToolRegistry) -> None:
    register_specs(registry, ALL_SPECS)
