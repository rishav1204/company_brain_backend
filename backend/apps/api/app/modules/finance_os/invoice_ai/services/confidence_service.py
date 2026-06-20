from __future__ import annotations

from app.modules.finance_os.invoice_ai.ai.confidence_scorer import auto_draft_eligible, confidence_band, overall_confidence
from app.modules.finance_os.invoice_ai.repositories.extraction_repository import ExtractionRepository

from app.services.db import get_db_conn, set_rls_org

extraction_repository = ExtractionRepository()


class ConfidenceService:
    def evaluate(
        self,
        *,
        extraction: dict,
        predictions: list[dict],
        duplicate_status: str,
        anomaly_count: int,
    ) -> dict:
        pred_scores = [float(p.get("confidence_score") or 0) for p in predictions]
        ext_conf = float(extraction.get("extraction_confidence") or 0)
        overall = overall_confidence(
            ext_conf,
            pred_scores,
            duplicate_status,
            anomaly_count,
        )
        band = confidence_band(overall)
        eligible = auto_draft_eligible(overall, duplicate_status, anomaly_count)
        return {
            "overall_confidence": overall,
            "confidence_band": band,
            "auto_draft_eligible": eligible,
        }

    def update_extraction_band(self, org_id: str, extraction_id: str, band: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.invoice_extractions
                    SET confidence_band = %s
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (band, org_id, extraction_id),
                )


confidence_service = ConfidenceService()
