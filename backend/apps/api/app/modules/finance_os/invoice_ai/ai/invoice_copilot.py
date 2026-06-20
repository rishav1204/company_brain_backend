from __future__ import annotations

from app.services.llm_provider import LlmProvider


class InvoiceCopilot:
    def __init__(self) -> None:
        self._llm = LlmProvider()

    def answer(self, org_id: str, *, question: str, context: str) -> str:
        if not self._llm.is_ready():
            return (
                "LLM is not configured. Based on extracted data: "
                f"{context[:500]}"
            )
        return self._llm.generate_text(
            org_id=org_id,
            system_prompt=(
                "You are an invoice intelligence copilot for accounts payable. "
                "Answer briefly using only the provided invoice context."
            ),
            user_prompt=f"Context:\n{context}\n\nQuestion: {question}",
            estimated_tokens=1200,
        )
