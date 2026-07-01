"""Bridge domain copilots (M27/M28/M32/M33) to the shared Platform Context Engine."""

from __future__ import annotations

from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.context.platform_context_engine import platform_context_engine
from app.modules.finance_os.platform_ai_runtime.context.prompt_assembler import prompt_assembler
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState, WorldStateScreen


def build_unified_context(
    org_id: str,
    question: str,
    *,
    module_hint: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> str:
    """Return compressed context text for domain copilots when M38_UNIFIED_COPILOT is enabled."""
    if not settings.m38_unified_copilot:
        return ""
    screen = WorldStateScreen(
        module=module_hint,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    ws = WorldState(screen=screen)
    ctx = platform_context_engine.build(org_id, message=question, world_state=ws)
    return prompt_assembler.build_planner_context_block(ctx)
