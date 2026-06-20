from __future__ import annotations

from app.services.llm_provider import LlmProvider


class WorkflowCopilot:
    def __init__(self) -> None:
        self._llm = LlmProvider()

    def answer(self, org_id: str, *, question: str, context: str) -> str:
        if not self._llm.is_ready():
            return f"Workflow intelligence summary: {context[:600]}"
        return self._llm.generate_text(
            org_id=org_id,
            system_prompt=(
                "You are a workflow intelligence copilot for finance operations. "
                "Explain bottlenecks, SLA risks, and optimization recommendations. Advisory only."
            ),
            user_prompt=f"Context:\n{context}\n\nQuestion: {question}",
            estimated_tokens=1500,
        )
