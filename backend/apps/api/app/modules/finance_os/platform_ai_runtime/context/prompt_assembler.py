from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import PlatformContext


def _screen_block(ctx: PlatformContext) -> str:
    ws = ctx.world_state
    if not ws or not ws.screen:
        return ""
    parts = []
    if ws.screen.module:
        parts.append(f"Module: {ws.screen.module}")
    if ws.screen.route:
        parts.append(f"Route: {ws.screen.route}")
    if ws.screen.entity_type:
        parts.append(f"Entity: {ws.screen.entity_type} {ws.screen.entity_id or ''}".strip())
    return "\n".join(parts)


class PromptAssembler:
    def build_answer_prompt(self, ctx: PlatformContext, question: str) -> tuple[str, str]:
        system = (
            "You are FLORA, a finance platform copilot. Answer using ONLY the supplied context. "
            "Be concise, factual, and cite which section you used. "
            "If data is insufficient, say what is missing. Read-only — do not propose mutations."
        )
        sections = [
            "## Company context",
            _screen_block(ctx) or "No screen context.",
            "## Policies",
            ctx.summaries.get("policies", "None flagged."),
            "## Permissions",
            ", ".join(ctx.world_state.permissions or []) or "default",
            "## Relevant data",
        ]
        for key, text in ctx.summaries.items():
            if key in {"policies", "conversation"}:
                continue
            sections.append(f"### {key}\n{text}")

        if ctx.entities:
            ent_lines = [f"- {e.entity_type}: {e.entity_id or e.label or 'inferred'}" for e in ctx.entities[:8]]
            sections.append("## Resolved entities\n" + "\n".join(ent_lines))

        sections.append(f"## User question\n{question}")
        return system, "\n\n".join(sections)

    def fallback_text(self, ctx: PlatformContext) -> str:
        parts = ["Based on available platform context:"]
        for key, text in ctx.summaries.items():
            if text:
                parts.append(f"\n[{key}]\n{text[:500]}")
        if not ctx.summaries:
            parts.append("No structured context retrieved yet.")
        return "\n".join(parts)

    def build_planner_context_block(self, ctx: PlatformContext) -> str:
        lines = [f"Intent: {ctx.intent.intent} (confidence {ctx.intent.confidence})"]
        if ctx.entities:
            lines.append("Entities: " + ", ".join(f"{e.entity_type}:{e.entity_id or '?'}" for e in ctx.entities[:6]))
        for key, text in list(ctx.summaries.items())[:8]:
            lines.append(f"{key}: {text[:400]}")
        return "\n".join(lines)


prompt_assembler = PromptAssembler()
