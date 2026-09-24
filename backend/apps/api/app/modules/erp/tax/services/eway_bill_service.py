from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.modules.erp.tax.events.tax_events import emit_eway_bill_created
from app.modules.erp.tax.repositories.compliance_repository import eway_bill_repository
from app.modules.platform.integrations.adapters.canonical_models import CanonicalEwayBill
from app.modules.platform.integrations.connectors.gst.gst_connector_resolver import resolve_eway_connector
from app.services.db import get_db_conn, set_rls_org


class EwayBillService:
    def generate(self, org_id: str, *, source_type: str, source_id: str, distance_km: int | None = None) -> dict:
        connector = resolve_eway_connector()
        if not connector or not hasattr(connector, "generate_eway_bill"):
            raise ValueError("E-way bill connector not available")
        result = connector.generate_eway_bill(
            idempotency_key=f"{org_id}:{source_type}:{source_id}",
            payload={"source_type": source_type, "source_id": source_id, "distance_km": distance_km},
        )
        if isinstance(result, CanonicalEwayBill):
            eway_no = result.eway_bill_no
            valid_upto = result.valid_upto
            raw = result.raw or {}
        else:
            eway_no = result.get("eway_bill_no")
            valid_upto = result.get("valid_upto")
            raw = result
        if not valid_upto:
            valid_upto = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        row = eway_bill_repository.create(
            org_id,
            source_type=source_type,
            source_id=source_id,
            eway_bill_no=eway_no,
            valid_upto=valid_upto,
            status="generated",
            raw_response=raw if isinstance(raw, dict) else {"result": raw},
        )
        emit_eway_bill_created(org_id, eway_bill_id=str(row["id"]), eway_bill_no=str(eway_no or ""))
        return row

    def maybe_auto_generate(self, org_id: str, *, source_type: str, source_id: str, taxable_value: float) -> dict | None:
        from app.modules.platform.regulatory.services.regulatory_resolver import (
            RegulatoryConfigError,
            regulatory_resolver,
        )

        try:
            min_amount = regulatory_resolver.resolve_threshold_amount(
                "gst.eway_bill_min", org_id=org_id, required=True
            )
        except RegulatoryConfigError as exc:
            raise ValueError(str(exc)) from exc
        if taxable_value < min_amount:
            return None
        return self.generate(org_id, source_type=source_type, source_id=source_id)

    def cancel(self, org_id: str, *, eway_bill_id: str, reason: str = "") -> dict:
        row = eway_bill_repository.get(org_id, eway_bill_id=eway_bill_id)
        if not row or not row.get("eway_bill_no"):
            raise ValueError("E-way bill not found")
        connector = resolve_eway_connector()
        if connector and hasattr(connector, "cancel_eway_bill"):
            connector.cancel_eway_bill(eway_bill_no=str(row["eway_bill_no"]), reason=reason)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE erp.eway_bills SET status='cancelled', updated_at=NOW() WHERE org_id=%s::uuid AND id=%s::uuid RETURNING id::text, status",
                    (org_id, eway_bill_id),
                )
                updated = cur.fetchone()
                return dict(updated) if updated else row

    def get(self, org_id: str, *, eway_bill_id: str) -> dict | None:
        return eway_bill_repository.get(org_id, eway_bill_id=eway_bill_id)


eway_bill_service = EwayBillService()
