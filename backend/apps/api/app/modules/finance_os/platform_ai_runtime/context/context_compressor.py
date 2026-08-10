from __future__ import annotations

import json
from typing import Any

from app.modules.finance_os.memory.engine.summarization_engine import summarize_entries
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import PlatformContext

CHARS_PER_TOKEN = 4
DEFAULT_TOKEN_BUDGET = 8000
TOP_N = 5


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _as_list(val: Any) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        for k in ("items", "data", "results", "rows", "records"):
            if isinstance(val.get(k), list):
                return val[k]
    return []


def _money(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _row_keys(row: dict) -> list[str]:
    preferred = (
        "id",
        "invoice_id",
        "vendor_id",
        "number",
        "invoice_number",
        "status",
        "amount",
        "total",
        "balance",
        "due_date",
        "risk",
        "exception",
    )
    keys = [k for k in preferred if k in row]
    if not keys:
        keys = list(row.keys())[:6]
    return keys


def _format_row(row: dict) -> str:
    keys = _row_keys(row)
    return ", ".join(f"{k}={row.get(k)}" for k in keys if row.get(k) is not None)


def _detect_exceptions(rows: list[dict]) -> list[str]:
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").lower()
        if status in {"blocked", "exception", "failed", "rejected", "overdue"}:
            out.append(_format_row(row))
        elif row.get("exception") or row.get("exception_type") or row.get("risk") in {"high", "critical"}:
            out.append(_format_row(row))
        elif row.get("overdue") is True:
            out.append(_format_row(row))
    return out[:TOP_N]


def _summarize_collection(label: str, items: list) -> str:
    if not items:
        return ""
    rows = [r for r in items if isinstance(r, dict)]
    non_dicts = [r for r in items if not isinstance(r, dict)]
    lines = [f"{label}: count={len(items)}"]
    # Totals when amounts present
    amount_keys = ("amount", "total", "balance", "grand_total", "outstanding")
    totals: dict[str, float] = {}
    for row in rows:
        for ak in amount_keys:
            m = _money(row.get(ak))
            if m is not None:
                totals[ak] = totals.get(ak, 0.0) + m
    if totals:
        lines.append("totals: " + ", ".join(f"{k}={round(v, 2)}" for k, v in totals.items()))
    # Top records — largest balance/total/amount
    scored = []
    for row in rows:
        score = 0.0
        for ak in ("balance", "total", "amount", "grand_total"):
            m = _money(row.get(ak))
            if m is not None:
                score = max(score, abs(m))
        scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [r for _, r in scored[:TOP_N]] or rows[:TOP_N]
    if top:
        lines.append("top_records:")
        for r in top:
            lines.append(f"  - {_format_row(r)}")
    exceptions = _detect_exceptions(rows)
    if exceptions:
        lines.append("exceptions:")
        for ex in exceptions:
            lines.append(f"  - {ex}")
    risk = []
    for row in rows:
        if isinstance(row, dict) and (row.get("risk") or row.get("risk_score")):
            risk.append(_format_row(row))
    if risk[:3]:
        lines.append("risk_indicators:")
        for r in risk[:3]:
            lines.append(f"  - {r}")
    if non_dicts:
        lines.append("other: " + ", ".join(str(x) for x in non_dicts[:TOP_N]))
    if len(items) > TOP_N:
        lines.append(f"... {len(items) - TOP_N} additional records omitted (expand on request)")
    return "\n".join(lines)


def _summarize_erp_facts(erp_facts: dict) -> dict[str, str]:
    summaries: dict[str, str] = {}
    for key, val in erp_facts.items():
        if not val:
            continue
        items = _as_list(val)
        if items and all(isinstance(x, dict) or not isinstance(x, dict) for x in items):
            # Prefer structured list compression for list-like results
            if any(isinstance(x, dict) for x in items) or len(items) > 1:
                summaries[key] = _summarize_collection(key, items)
                continue
        if isinstance(val, dict):
            # Single object snapshot — compact JSON, no hallucination
            compact = {k: val.get(k) for k in list(val.keys())[:20]}
            summaries[key] = json.dumps(compact, default=str)[:1200]
        elif isinstance(val, list):
            summaries[key] = _summarize_collection(key, val)
        else:
            summaries[key] = str(val)[:800]
    return summaries


class ContextCompressor:
    """Compress structured data to summary/totals/top/exceptions — never invent values."""

    def compress(self, ctx: PlatformContext, *, token_budget: int | None = None) -> PlatformContext:
        if token_budget is None:
            try:
                from app.services.ai_gateway.context_budget import context_budget_engine
                from app.services.ai_gateway.types import ExecutionClass
                from app.core.config import settings

                token_budget = context_budget_engine.compressor_budget(
                    ExecutionClass.ANSWER, model=settings.openai_model
                )
            except Exception:
                token_budget = DEFAULT_TOKEN_BUDGET
        summaries: dict[str, str] = dict(ctx.summaries)

        if ctx.memory:
            mem_text = summarize_entries(ctx.memory, max_chars=1500)
            if not mem_text:
                mem_text = _summarize_collection("Memory", ctx.memory)
            summaries["memory"] = mem_text

        if ctx.graph:
            summaries["graph"] = _summarize_collection("Graph relationships", ctx.graph)

        if ctx.documents:
            doc_lines = [str(d.get("content", ""))[:300] for d in ctx.documents[:5] if isinstance(d, dict)]
            summaries["documents"] = "Documents (top " + str(len(doc_lines)) + "):\n" + "\n".join(doc_lines)

        erp_summaries = _summarize_erp_facts(ctx.erp_facts)
        summaries.update(erp_summaries)

        if ctx.approval_queue:
            summaries["approvals"] = _summarize_collection("Approval queue", ctx.approval_queue)

        if ctx.workflow_state:
            summaries["workflows"] = _summarize_collection("Active workflows", ctx.workflow_state)

        if ctx.recent_events:
            summaries["recent_events"] = _summarize_collection("Recent events", ctx.recent_events)

        if ctx.policies:
            summaries["policies"] = "Policy flags: " + json.dumps(ctx.policies[:10], default=str)[:600]

        wm = ctx.working_memory
        if wm.turn_count or wm.current_task:
            parts = [
                f"Turn {wm.turn_count}",
                f"last_intent={wm.last_intent}",
                f"task={wm.current_task}" if wm.current_task else None,
                f"period={wm.current_period}" if wm.current_period else None,
                f"entity={wm.current_entity}" if wm.current_entity else None,
            ]
            if wm.current_comparisons:
                parts.append(f"comparisons={wm.current_comparisons[:3]}")
            if wm.reasoning_chain:
                parts.append(f"reasoning_tail={wm.reasoning_chain[-3:]}")
            summaries["conversation"] = "; ".join(str(p) for p in parts if p)

        # World state is carried separately in assembler; keep a compact note for tokens
        ws = ctx.world_state
        if ws and ws.screen:
            summaries["ui_location"] = (
                f"module={ws.screen.module} route={ws.screen.route} "
                f"entity={ws.screen.entity_type}:{ws.screen.entity_id}"
            )

        token_estimate = _estimate_tokens(" ".join(summaries.values()))
        if token_estimate > token_budget:
            ratio = token_budget / max(token_estimate, 1)
            for key in list(summaries.keys()):
                cap = max(80, int(len(summaries[key]) * ratio))
                summaries[key] = summaries[key][:cap]
            token_estimate = token_budget

        return ctx.model_copy(update={"summaries": summaries, "token_estimate": token_estimate})


context_compressor = ContextCompressor()
