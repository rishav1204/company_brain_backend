from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib import error, request

from app.modules.platform.integrations.adapters.canonical_models import CanonicalEInvoice, CanonicalGSTReturn
from app.modules.platform.integrations.connectors.gst.gst_connector_resolver import load_gst_connector_config
from app.modules.platform.integrations.connectors.gst.stub_gst_connector import StubGstConnector
from app.modules.platform.integrations.services.connector_registry import connector_registry


class _HttpGstMixin:
    def _post_json(self, url: str, payload: dict, *, headers: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req_headers = {"Content-Type": "application/json", **(headers or {})}
        req = request.Request(url, data=body, headers=req_headers, method="POST")
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))


class ProductionGstnConnector(_HttpGstMixin):
    """GSTN portal connector — uses GSTN_BASE_URL + credentials when configured."""

    connector_type = "gst"
    provider_name = "gstn_production"

    def health(self) -> dict:
        cfg = load_gst_connector_config()
        return {"ready": cfg.gstn_configured, "provider": self.provider_name, "base_url": cfg.gstn_base_url}

    def submit_return(self, *, idempotency_key: str, payload: dict) -> CanonicalGSTReturn:
        cfg = load_gst_connector_config()
        if not cfg.gstn_configured:
            return StubGstConnector().submit_return(idempotency_key=idempotency_key, payload=payload)
        try:
            url = f"{cfg.gstn_base_url.rstrip('/')}/returns/file"
            headers = {"X-API-Key": cfg.gstn_api_key} if cfg.gstn_api_key else {}
            if cfg.gstn_username:
                headers["X-GSTN-Username"] = cfg.gstn_username
            result = self._post_json(url, {"idempotency_key": idempotency_key, **payload}, headers=headers)
            return CanonicalGSTReturn(
                return_period=str(payload.get("return_period") or ""),
                status=str(result.get("status") or "submitted"),
                filed_at=str(result.get("filed_at") or datetime.now(timezone.utc).isoformat()),
                raw=result,
            )
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return StubGstConnector().submit_return(idempotency_key=idempotency_key, payload=payload)


class ProductionIrpConnector(_HttpGstMixin):
    connector_type = "irp"
    provider_name = "irp_production"

    def health(self) -> dict:
        cfg = load_gst_connector_config()
        return {"ready": cfg.irp_configured, "provider": self.provider_name}

    def generate_irn(self, *, idempotency_key: str, payload: dict) -> CanonicalEInvoice:
        cfg = load_gst_connector_config()
        if not cfg.irp_configured:
            stub = connector_registry.resolve(connector_type="irp", provider_name="gstn_irp")
            if stub and hasattr(stub, "generate_irn"):
                return stub.generate_irn(idempotency_key=idempotency_key, payload=payload)
            return StubGstConnector().generate_irn(idempotency_key=idempotency_key, payload=payload)  # type: ignore[return-value]
        try:
            url = f"{cfg.irp_base_url.rstrip('/')}/einvoice/generate"
            result = self._post_json(
                url,
                {"idempotency_key": idempotency_key, **payload},
                headers={"X-Client-Id": cfg.irp_client_id, "X-Client-Secret": cfg.irp_client_secret},
            )
            return CanonicalEInvoice(
                irn=str(result.get("irn") or ""),
                ack_no=str(result.get("ack_no") or ""),
                ack_date=str(result.get("ack_date") or datetime.now(timezone.utc).isoformat()),
                qr_code=str(result.get("qr_code") or ""),
                status=str(result.get("status") or "generated"),
                raw=result,
            )
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            stub = connector_registry.resolve(connector_type="irp", provider_name="gstn_irp")
            if stub and hasattr(stub, "generate_irn"):
                return stub.generate_irn(idempotency_key=idempotency_key, payload=payload)
            raise

    def cancel_irn(self, *, irn: str, reason: str = "") -> dict:
        cfg = load_gst_connector_config()
        if not cfg.irp_configured:
            stub = connector_registry.resolve(connector_type="irp", provider_name="gstn_irp")
            if stub and hasattr(stub, "cancel_irn"):
                return stub.cancel_irn(irn=irn, reason=reason)
            return {"irn": irn, "status": "cancelled", "reason": reason}
        try:
            url = f"{cfg.irp_base_url.rstrip('/')}/einvoice/cancel"
            return self._post_json(
                url,
                {"irn": irn, "reason": reason},
                headers={"X-Client-Id": cfg.irp_client_id, "X-Client-Secret": cfg.irp_client_secret},
            )
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return {"irn": irn, "status": "cancelled", "reason": reason}


class ProductionEwayConnector(_HttpGstMixin):
    connector_type = "eway"
    provider_name = "eway_production"

    def health(self) -> dict:
        cfg = load_gst_connector_config()
        return {"ready": cfg.eway_configured, "provider": self.provider_name}

    def generate_eway_bill(self, *, idempotency_key: str, payload: dict) -> dict:
        cfg = load_gst_connector_config()
        if not cfg.eway_configured:
            return StubGstConnector().generate_eway_bill(idempotency_key=idempotency_key, payload=payload)
        try:
            url = f"{cfg.eway_base_url.rstrip('/')}/ewaybill/generate"
            return self._post_json(
                url,
                {"idempotency_key": idempotency_key, **payload},
                headers={"X-Eway-Username": cfg.eway_username, "X-Eway-Password": cfg.eway_password},
            )
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return StubGstConnector().generate_eway_bill(idempotency_key=idempotency_key, payload=payload)

    def cancel_eway_bill(self, *, eway_bill_no: str, reason: str = "") -> dict:
        cfg = load_gst_connector_config()
        if not cfg.eway_configured:
            return StubGstConnector().cancel_eway_bill(eway_bill_no=eway_bill_no, reason=reason)
        try:
            url = f"{cfg.eway_base_url.rstrip('/')}/ewaybill/cancel"
            return self._post_json(
                url,
                {"eway_bill_no": eway_bill_no, "reason": reason},
                headers={"X-Eway-Username": cfg.eway_username, "X-Eway-Password": cfg.eway_password},
            )
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return StubGstConnector().cancel_eway_bill(eway_bill_no=eway_bill_no, reason=reason)


connector_registry.register(ProductionGstnConnector())
connector_registry.register(ProductionIrpConnector())
connector_registry.register(ProductionEwayConnector())
