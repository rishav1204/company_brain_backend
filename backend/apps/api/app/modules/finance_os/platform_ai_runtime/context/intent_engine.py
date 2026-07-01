from __future__ import annotations

import re

from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import IntentResult, IntentType
from app.services.llm_provider import llm_provider
from app.services.logger import log_event

_READ_SIGNALS = (
    "list", "show", "get", "how much", "how many", "what is", "what are", "why is", "why are",
    "explain", "compare", "display", "tell me", "summarize", "summary", "status of", "pending",
)
_ACTION_SIGNALS = (
    "create", "buy", "purchase", "submit", "confirm", "receive", "pay", "approve", "capitalize",
    "cancel", "delete", "update", "draft", "order", "procure", "post", "file",
)
_WORKFLOW_SIGNALS = ("workflow", "escalate", "assign", "start follow", "launch", "follow up")
_ANALYSIS_SIGNALS = (
    "trend", "root cause", "forecast", "anomaly", "falling", "lower", "higher", "compare with",
    "cash flow", "analysis", "insight", "driver",
)
_MIXED_CONNECTORS = (" then ", " and then ", " after that ", " followed by ")

_MODULE_HINTS: dict[str, tuple[str, ...]] = {
    "gst": ("gst", "cgst", "sgst", "igst", "tax return", "tax paid"),
    "ap": ("vendor", "payable", "ap ", "invoice", "payment late", "overdue ap"),
    "ar": ("receivable", "ar ", "collections", "overdue", "customer"),
    "treasury": ("cash", "bank balance", "liquidity", "treasury"),
    "procurement": ("po", "purchase order", "grn", "procure", "vendor order"),
    "inventory": ("stock", "inventory", "on hand", "warehouse"),
    "gl": ("journal", "trial balance", "ledger", "gl "),
    "analytics": ("kpi", "dashboard", "executive", "board"),
}


def _has_action_signal(text: str) -> bool:
    for verb in _ACTION_SIGNALS:
        if verb in {"pay"}:
            if re.search(r"\b(pay|pays|paying)\b", text) and not re.search(r"\b(paid|payment)\b", text):
                return True
            continue
        if verb in text:
            return True
    return False


def _heuristic_classify(message: str) -> IntentResult:
    text = message.lower().strip()
    has_read = any(s in text for s in _READ_SIGNALS)
    has_action = _has_action_signal(text)
    has_workflow = any(s in text for s in _WORKFLOW_SIGNALS)
    has_analysis = any(s in text for s in _ANALYSIS_SIGNALS)
    has_mixed = any(c in text for c in _MIXED_CONNECTORS)

    modules: list[str] = []
    for mod, keys in _MODULE_HINTS.items():
        if any(k in text for k in keys):
            modules.append(mod)

    if has_mixed or (has_read and has_action and not re.search(r"\b(how much|how many|what is|what are)\b", text)):
        return IntentResult(intent="mixed", confidence=0.78, sub_intents=["read", "action"], suggested_modules=modules)
    if has_read and re.search(r"\b(how much|how many|what is|what are|why is|why are)\b", text):
        intent: IntentType = "analysis" if has_analysis else "read"
        return IntentResult(intent=intent, confidence=0.85, suggested_modules=modules)
    if has_workflow and not has_action:
        return IntentResult(intent="workflow", confidence=0.8, suggested_modules=modules or ["workflow"])
    if has_analysis and not has_action:
        return IntentResult(intent="analysis", confidence=0.82, suggested_modules=modules or ["analytics", "treasury"])
    if has_action and not has_read:
        return IntentResult(intent="action", confidence=0.85, suggested_modules=modules)
    if has_read or text.endswith("?"):
        return IntentResult(intent="read", confidence=0.8, suggested_modules=modules)
    if has_action:
        return IntentResult(intent="action", confidence=0.7, suggested_modules=modules)
    return IntentResult(intent="read", confidence=0.55, suggested_modules=modules)


def _llm_classify(message: str) -> IntentResult | None:
    if not llm_provider.is_ready():
        return None
    try:
        raw = llm_provider.generate_json(
            org_id="platform-context",
            system_prompt=(
                "Classify finance copilot intent. Output JSON only: "
                "{intent: read|action|workflow|analysis|mixed, confidence: 0-1, "
                "sub_intents: [], suggested_modules: []}"
            ),
            user_prompt=f"User message: {message}",
            estimated_tokens=400,
        )
        if not isinstance(raw, dict):
            return None
        intent = str(raw.get("intent") or "read")
        if intent not in {"read", "action", "workflow", "analysis", "mixed"}:
            intent = "read"
        return IntentResult(
            intent=intent,  # type: ignore[arg-type]
            confidence=float(raw.get("confidence") or 0.7),
            sub_intents=[str(x) for x in (raw.get("sub_intents") or [])],
            suggested_modules=[str(x) for x in (raw.get("suggested_modules") or [])],
        )
    except Exception as exc:
        log_event("m38.context.intent_llm_failed", detail=str(exc))
        return None


class IntentEngine:
    def classify(self, message: str, *, use_llm: bool = True) -> IntentResult:
        result = _heuristic_classify(message)
        if result.confidence >= 0.75 or not use_llm or not settings.m38_context_engine_enabled:
            return result
        llm_result = _llm_classify(message)
        if llm_result and llm_result.confidence > result.confidence:
            return llm_result
        return result


intent_engine = IntentEngine()
