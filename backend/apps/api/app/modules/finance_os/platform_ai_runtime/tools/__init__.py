from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.tools.catalog import register_catalog
from app.modules.finance_os.platform_ai_runtime.tools.registry import tool_registry


def _register_all() -> None:
    register_catalog(tool_registry)


_register_all()
