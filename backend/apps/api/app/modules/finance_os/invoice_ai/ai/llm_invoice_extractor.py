from __future__ import annotations

import json
from typing import Any

from app.modules.finance_os.invoice_ai.ai.invoice_extractor import extract_regex
from app.services.llm_provider import LlmProvider

_LLM_SYSTEM = """You extract structured invoice data from OCR text.
Return JSON only with keys: invoice_number, vendor_name, vendor_gstin, invoice_date (YYYY-MM-DD),
due_date (YYYY-MM-DD or null), taxable_amount, gst_amount, total_amount, line_items (array of
{description, amount, gst_rate}), confidence (0-1). Use null for unknown fields."""


class InvoiceExtractor:
    def __init__(self) -> None:
        self._llm = LlmProvider()

    def extract(self, org_id: str, text: str) -> dict[str, Any]:
        regex_result = extract_regex(text)
        if not self._llm.is_ready():
            return regex_result

        try:
            llm_data = self._llm.generate_json(
                org_id=org_id,
                system_prompt=_LLM_SYSTEM,
                user_prompt=f"Extract invoice fields from:\n\n{text[:12000]}",
                estimated_tokens=2000,
            )
            merged = self._merge(regex_result, llm_data)
            merged["method"] = "regex+llm"
            return merged
        except Exception:
            return regex_result

    def _merge(self, regex_result: dict, llm_data: dict) -> dict[str, Any]:
        out = dict(regex_result)
        for key in (
            "invoice_number",
            "vendor_name",
            "vendor_gstin",
            "invoice_date",
            "due_date",
            "taxable_amount",
            "gst_amount",
            "total_amount",
        ):
            llm_val = llm_data.get(key)
            if llm_val is not None and llm_val != "":
                out[key] = llm_val
        llm_conf = float(llm_data.get("confidence") or 0)
        out["extraction_confidence"] = max(
            float(regex_result.get("extraction_confidence") or 0),
            llm_conf,
        )
        out["line_items"] = llm_data.get("line_items") or []
        out["raw_llm"] = llm_data
        return out
