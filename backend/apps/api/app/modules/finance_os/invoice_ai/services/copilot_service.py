from __future__ import annotations

import json

from app.modules.finance_os.invoice_ai.ai.invoice_copilot import InvoiceCopilot
from app.modules.finance_os.invoice_ai.services.extraction_service import extraction_service
from app.modules.finance_os.invoice_ai.services.duplicate_service import duplicate_service
from app.modules.finance_os.invoice_ai.services.anomaly_service import anomaly_service
from app.modules.finance_os.invoice_ai.repositories.prediction_repository import PredictionRepository

prediction_repository = PredictionRepository()


class CopilotService:
    def __init__(self) -> None:
        self._copilot = InvoiceCopilot()

    def answer(self, org_id: str, *, extraction_id: str, question: str) -> str:
        extraction = extraction_service.get(org_id, extraction_id)
        if not extraction:
            return "Extraction not found."
        predictions = prediction_repository.list_for_extraction(org_id, extraction_id)
        dup = duplicate_service.latest(org_id, extraction_id)
        anomalies = anomaly_service.list_for_extraction(org_id, extraction_id)
        context = json.dumps(
            {
                "extraction": extraction,
                "predictions": predictions,
                "duplicate": dup,
                "anomalies": anomalies,
            },
            default=str,
        )[:8000]
        return self._copilot.answer(org_id, question=question, context=context)


copilot_service = CopilotService()
