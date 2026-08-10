"""Execution classification — deterministic vs AI routing (Wave 6)."""

from __future__ import annotations

import re

from app.services.ai_gateway.types import ExecutionClass


_CRUD_PATTERNS = re.compile(
    r"\b(create|add|update|delete|remove|save|edit)\b.+\b(vendor|customer|item|account|branch)\b",
    re.I,
)
_RETRIEVAL_PATTERNS = re.compile(
    r"\b(show|list|get|display|fetch|find|status of|what is|how much|how many)\b",
    re.I,
)
_REASONING_PATTERNS = re.compile(
    r"\b(why|explain|root cause|trend|forecast|anomaly|compare|because|driver|insight)\b",
    re.I,
)
_PLANNING_PATTERNS = re.compile(
    r"\b(plan|close books|period close|month-end|quarter|procure|orchestrat|multi-step|campaign)\b",
    re.I,
)
_WORKFLOW_PATTERNS = re.compile(
    r"\b(workflow|approve|escalat|follow up|collection|launch|start process)\b",
    re.I,
)
_LONG_GOAL = re.compile(
    r"\b(dso|reduce overdue|cash position over weeks|quarter-end|long.?running)\b",
    re.I,
)


class ExecutionClassifier:
    def classify(
        self,
        *,
        text: str = "",
        operation_code: str | None = None,
        explicit: ExecutionClass | str | None = None,
        intent: str | None = None,
        require_json: bool = False,
    ) -> tuple[ExecutionClass, str, float]:
        """Returns (class, reason, complexity 0..1)."""
        if explicit:
            try:
                ec = ExecutionClass(str(explicit))
                return ec, f"explicit:{ec.value}", self._complexity(ec)
            except ValueError:
                pass

        op = (operation_code or "").lower()
        if "embed" in op or op.endswith("embedding"):
            return ExecutionClass.EMBEDDING, "operation:embedding", 0.2
        if "ocr" in op or "vision" in op:
            return ExecutionClass.OCR_VISION, "operation:ocr", 0.5
        if "intent" in op:
            return ExecutionClass.INTENT_CLASSIFY, "operation:intent", 0.25
        if "plan" in op or "m38_plan" in op:
            return ExecutionClass.PLANNING, "operation:plan", 0.75
        if "answer" in op or "m38_answer" in op:
            return ExecutionClass.ANSWER, "operation:answer", 0.55
        if "retrieval" in op:
            return ExecutionClass.RETRIEVAL, "operation:retrieval", 0.4

        if intent:
            mapping = {
                "read": ExecutionClass.RETRIEVAL,
                "analysis": ExecutionClass.REASONING,
                "action": ExecutionClass.DETERMINISTIC_TOOL,
                "workflow": ExecutionClass.AGENTIC_WORKFLOW,
                "mixed": ExecutionClass.PLANNING,
            }
            if intent in mapping:
                ec = mapping[intent]
                return ec, f"intent:{intent}", self._complexity(ec)

        t = text or ""
        if not t.strip():
            return ExecutionClass.REASONING, "empty_default", 0.5

        if _CRUD_PATTERNS.search(t) and not _REASONING_PATTERNS.search(t):
            return ExecutionClass.DETERMINISTIC_TOOL, "pattern:crud_tool", 0.2
        if _LONG_GOAL.search(t):
            return ExecutionClass.LONG_RUNNING_GOAL, "pattern:long_goal", 0.85
        if _PLANNING_PATTERNS.search(t) and (_WORKFLOW_PATTERNS.search(t) or "step" in t.lower()):
            return ExecutionClass.PLANNING, "pattern:planning", 0.8
        if _REASONING_PATTERNS.search(t):
            return ExecutionClass.REASONING, "pattern:reasoning", 0.65
        if _WORKFLOW_PATTERNS.search(t):
            return ExecutionClass.AGENTIC_WORKFLOW, "pattern:workflow", 0.7
        if _RETRIEVAL_PATTERNS.search(t) and not require_json:
            return ExecutionClass.RETRIEVAL, "pattern:retrieval", 0.35
        if _RETRIEVAL_PATTERNS.search(t):
            return ExecutionClass.ANSWER, "pattern:retrieval_answer", 0.45

        return ExecutionClass.REASONING, "default:reasoning", 0.55

    def should_skip_llm(self, execution_class: ExecutionClass, *, complexity: float, heuristic_confidence: float | None = None) -> bool:
        if execution_class in {ExecutionClass.NO_AI, ExecutionClass.DETERMINISTIC_TOOL}:
            return True
        if execution_class == ExecutionClass.INTENT_CLASSIFY and heuristic_confidence is not None and heuristic_confidence >= 0.75:
            return True
        if execution_class == ExecutionClass.RETRIEVAL and complexity < 0.3:
            # pure show/list can often use deterministic tools only
            return False  # retrieval still may need NL answer — keep AI optional at caller
        return False

    def _complexity(self, ec: ExecutionClass) -> float:
        return {
            ExecutionClass.NO_AI: 0.0,
            ExecutionClass.DETERMINISTIC_TOOL: 0.15,
            ExecutionClass.RETRIEVAL: 0.35,
            ExecutionClass.INTENT_CLASSIFY: 0.25,
            ExecutionClass.EMBEDDING: 0.2,
            ExecutionClass.OCR_VISION: 0.5,
            ExecutionClass.ANSWER: 0.5,
            ExecutionClass.REASONING: 0.65,
            ExecutionClass.AGENTIC_WORKFLOW: 0.7,
            ExecutionClass.PLANNING: 0.8,
            ExecutionClass.LONG_RUNNING_GOAL: 0.9,
        }.get(ec, 0.5)


execution_classifier = ExecutionClassifier()
