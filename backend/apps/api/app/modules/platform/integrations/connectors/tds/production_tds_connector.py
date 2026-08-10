from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib import error, request

from app.modules.platform.integrations.adapters.canonical_models import CanonicalTdsReturn
from app.modules.platform.integrations.connectors.tds.stub_tds_connector import StubTdsConnector
from app.modules.platform.integrations.connectors.tds.tds_connector_resolver import load_tds_connector_config
from app.modules.platform.integrations.services.connector_registry import connector_registry


class _HttpTdsMixin:
    def _post_json(self, url: str, payload: dict, *, headers: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req_headers = {"Content-Type": "application/json", **(headers or {})}
        req = request.Request(url, data=body, headers=req_headers, method="POST")
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))


class ProductionNsdlTdsConnector(_HttpTdsMixin):
    connector_type = "tds"
    provider_name = "nsdl_production"

    def health(self) -> dict:
        cfg = load_tds_connector_config()
        return {"ready": cfg.nsdl_configured, "provider": self.provider_name, "base_url": cfg.nsdl_base_url}

    def submit_return(self, *, idempotency_key: str, payload: dict) -> CanonicalTdsReturn:
        cfg = load_tds_connector_config()
        if not cfg.nsdl_configured:
            return StubTdsConnector().submit_return(idempotency_key=idempotency_key, payload=payload)
        try:
            url = f"{cfg.nsdl_base_url.rstrip('/')}/tds/returns/file"
            result = self._post_json(
                url,
                {"idempotency_key": idempotency_key, "tan": cfg.nsdl_tan, **payload},
                headers={"X-NSDL-User": cfg.nsdl_user, "X-NSDL-Password": cfg.nsdl_password},
            )
            return CanonicalTdsReturn(
                return_period=str(payload.get("return_period") or ""),
                form_type=str(payload.get("form_type") or "26Q"),
                status=str(result.get("status") or "submitted"),
                acknowledgment_no=str(result.get("acknowledgment_no") or result.get("ack_no") or ""),
                filed_at=str(result.get("filed_at") or datetime.now(timezone.utc).isoformat()),
                raw=result,
            )
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            from app.modules.platform.integrations.connectors.connector_errors import fail_closed_in_prod

            fail_closed_in_prod(exc, operation="nsdl.submit_return")
            return StubTdsConnector().submit_return(idempotency_key=idempotency_key, payload=payload)

    def generate_fvu(self, *, payload: dict) -> dict:
        cfg = load_tds_connector_config()
        if not cfg.nsdl_configured:
            return StubTdsConnector().generate_fvu(payload=payload)
        try:
            url = f"{cfg.nsdl_base_url.rstrip('/')}/tds/fvu/generate"
            result = self._post_json(
                url,
                {"tan": cfg.nsdl_tan, **payload},
                headers={"X-NSDL-User": cfg.nsdl_user, "X-NSDL-Password": cfg.nsdl_password},
            )
            return {
                "fvu_file_name": result.get("fvu_file_name"),
                "fvu_payload": result.get("payload") or payload,
                "status": str(result.get("status") or "generated"),
                "provider": self.provider_name,
            }
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return StubTdsConnector().generate_fvu(payload=payload)

    def validate_challan(self, *, challan_no: str, bsr_code: str | None, amount: float) -> dict:
        cfg = load_tds_connector_config()
        if not cfg.nsdl_configured:
            return StubTdsConnector().validate_challan(challan_no=challan_no, bsr_code=bsr_code, amount=amount)
        try:
            url = f"{cfg.nsdl_base_url.rstrip('/')}/tds/challan/validate"
            return self._post_json(
                url,
                {"challan_no": challan_no, "bsr_code": bsr_code, "amount": amount, "tan": cfg.nsdl_tan},
                headers={"X-NSDL-User": cfg.nsdl_user, "X-NSDL-Password": cfg.nsdl_password},
            )
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return StubTdsConnector().validate_challan(challan_no=challan_no, bsr_code=bsr_code, amount=amount)


connector_registry.register(ProductionNsdlTdsConnector())
