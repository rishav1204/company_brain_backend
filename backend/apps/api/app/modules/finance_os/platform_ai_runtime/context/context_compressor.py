from __future__ import annotations

import json

from app.modules.finance_os.memory.engine.summarization_engine import summarize_entries
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import PlatformContext

CHARS_PER_TOKEN = 4
DEFAULT_TOKEN_BUDGET = 8000


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _summarize_list(items: list, *, label: str, max_items: int = 5) -> str:
    if not items:
        return ""
    if isinstance(items[0], dict):
        keys = list(items[0].keys())[:6]
        lines = [f"- {', '.join(f'{k}={row.get(k)}' for k in keys if row.get(k) is not None)}" for row in items[:max_items]]
        if len(items) > max_items:
            lines.append(f"... and {len(items) - max_items} more")
        return f"{label} ({len(items)} records):\n" + "\n".join(lines)
    return f"{label}: " + ", ".join(str(x) for x in items[:max_items])


def _summarize_erp_facts(erp_facts: dict) -> dict[str, str]:
    summaries: dict[str, str] = {}
    for key, val in erp_facts.items():
        if not val:
            continue
        if isinstance(val, dict):
            if val.get("items") and isinstance(val["items"], list):
                summaries[key] = _summarize_list(val["items"], label=key)
            elif val.get("data") and isinstance(val["data"], list):
                summaries[key] = _summarize_list(val["data"], label=key)
            else:
                summaries[key] = json.dumps(val, default=str)[:1200]
        elif isinstance(val, list):
            summaries[key] = _summarize_list(val, label=key)
        else:
            summaries[key] = str(val)[:800]
    return summaries


class ContextCompressor:
    def compress(self, ctx: PlatformContext, *, token_budget: int = DEFAULT_TOKEN_BUDGET) -> PlatformContext:
        summaries: dict[str, str] = dict(ctx.summaries)

        if ctx.memory:
            mem_text = summarize_entries(ctx.memory, max_chars=1500)
            if not mem_text:
                mem_text = _summarize_list(ctx.memory, label="Memory", max_items=5)
            summaries["memory"] = mem_text

        if ctx.graph:
            summaries["graph"] = _summarize_list(ctx.graph, label="Graph relationships", max_items=5)

        if ctx.documents:
            doc_lines = [str(d.get("content", ""))[:300] for d in ctx.documents[:5]]
            summaries["documents"] = "Documents:\n" + "\n".join(doc_lines)

        erp_summaries = _summarize_erp_facts(ctx.erp_facts)
        summaries.update(erp_summaries)

        if ctx.policies:
            summaries["policies"] = "Policy flags: " + json.dumps(ctx.policies[:10], default=str)[:600]

        if ctx.working_memory.turn_count:
            summaries["conversation"] = (
                f"Turn {ctx.working_memory.turn_count}; "
                f"last_intent={ctx.working_memory.last_intent}; "
                f"period={ctx.working_memory.current_period}"
            )

        total_chars = sum(len(v) for v in summaries.values())
        token_estimate = _estimate_tokens(" ".join(summaries.values()))

        if token_estimate > token_budget:
            ratio = token_budget / max(token_estimate, 1)
            for key in list(summaries.keys()):
                cap = max(80, int(len(summaries[key]) * ratio))
                summaries[key] = summaries[key][:cap]
            token_estimate = token_budget

        return ctx.model_copy(update={"summaries": summaries, "token_estimate": token_estimate})


context_compressor = ContextCompressor()
