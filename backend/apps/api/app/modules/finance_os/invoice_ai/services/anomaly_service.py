from __future__ import annotations

from app.modules.finance_os.invoice_ai.ai.anomaly_detector import detect_anomalies
from app.modules.finance_os.invoice_ai.repositories.anomaly_repository import AnomalyRepository
from app.services.db import get_db_conn, set_rls_org

anomaly_repository = AnomalyRepository()


class AnomalyService:
    def _vendor_stats(self, org_id: str, vendor_id: str | None) -> tuple[float | None, float | None]:
        if not vendor_id:
            return None, None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT AVG(total_amount)::float8 AS avg_amt, STDDEV(total_amount)::float8 AS std_amt
                    FROM erp.ap_invoices
                    WHERE org_id = %s::uuid AND vendor_id = %s::uuid
                    """,
                    (org_id, vendor_id),
                )
                row = cur.fetchone()
                if not row:
                    return None, None
                return row.get("avg_amt"), row.get("std_amt")

    def detect_and_persist(
        self,
        org_id: str,
        *,
        extraction: dict,
        duplicate_status: str,
    ) -> list[dict]:
        vendor_id = extraction.get("vendor_id")
        avg, std = self._vendor_stats(org_id, str(vendor_id) if vendor_id else None)
        conf = float(extraction.get("extraction_confidence") or 0)
        conf_norm = conf / 100 if conf > 1 else conf

        items = detect_anomalies(
            total_amount=float(extraction.get("total_amount") or 0),
            vendor_avg=avg,
            vendor_std=std,
            extraction_confidence=conf_norm,
            duplicate_status=duplicate_status,
        )

        total = float(extraction.get("total_amount") or 0)
        if total > 0 and total % 10000 == 0:
            items.append(
                {
                    "anomaly_type": "round_amount_fraud",
                    "anomaly_score": 0.5,
                    "severity": "low",
                    "description": f"Round amount detected: {total}",
                }
            )

        saved: list[dict] = []
        for item in items:
            score = float(item.get("anomaly_score") or 0)
            score_pct = score * 100 if score <= 1 else score
            saved.append(
                anomaly_repository.create(
                    org_id,
                    data={
                        "extraction_id": extraction["id"],
                        "anomaly_type": item["anomaly_type"],
                        "anomaly_score": score_pct,
                        "severity": item.get("severity", "medium"),
                        "description": item["description"],
                    },
                )
            )
        return saved

    def list_for_extraction(self, org_id: str, extraction_id: str) -> list[dict]:
        return anomaly_repository.list_for_extraction(org_id, extraction_id)

    def list_recent(self, org_id: str, limit: int = 200) -> list[dict]:
        return anomaly_repository.list_recent(org_id, limit=limit)


anomaly_service = AnomalyService()
