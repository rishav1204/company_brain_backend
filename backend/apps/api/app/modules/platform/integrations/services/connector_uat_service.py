from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib import error, request

from app.core.config import settings
from app.modules.platform.integrations.connectors.gst.gst_connector_resolver import load_gst_connector_config
from app.modules.platform.integrations.connectors.tds.tds_connector_resolver import load_tds_connector_config
from app.modules.platform.integrations.services.connector_registry import connector_registry


@dataclass
class ConnectorCheckResult:
    connector: str
    configured: bool
    reachable: bool
    status: str
    detail: str
    provider: str | None = None


def _http_ping(base_url: str, *, path: str = "/health", timeout: int = 10) -> tuple[bool, str]:
    if not base_url.strip():
        return False, "base_url_missing"
    url = f"{base_url.rstrip('/')}{path}"
    try:
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            return True, f"http_{resp.status}:{body[:120]}"
    except error.HTTPError as exc:
        if exc.code in {401, 403, 404, 405}:
            return True, f"http_{exc.code}:endpoint_reachable"
        return False, f"http_{exc.code}"
    except (error.URLError, TimeoutError, OSError) as exc:
        return False, str(exc)[:200]


def _required_env(keys: list[str]) -> tuple[bool, list[str]]:
    missing = [k for k in keys if not os.getenv(k, "").strip()]
    return len(missing) == 0, missing


class ConnectorUatService:
    """Production connector configuration + connectivity UAT (ERP-17/19/20)."""

    def check_gst(self) -> ConnectorCheckResult:
        cfg = load_gst_connector_config()
        configured = cfg.gstn_configured
        reachable = False
        detail = "not_configured"
        if configured:
            conn = connector_registry.resolve(connector_type="gst", provider_name="gstn_production")
            health = conn.health() if conn and hasattr(conn, "health") else {}
            reachable, ping_detail = _http_ping(cfg.gstn_base_url)
            detail = json.dumps({"health": health, "ping": ping_detail})
        return ConnectorCheckResult(
            connector="gst",
            configured=configured,
            reachable=reachable,
            status="ok" if configured and reachable else ("configured_unreachable" if configured else "not_configured"),
            detail=detail,
            provider="gstn_production",
        )

    def check_tds(self) -> ConnectorCheckResult:
        cfg = load_tds_connector_config()
        configured = cfg.nsdl_configured
        reachable = False
        detail = "not_configured"
        if configured:
            conn = connector_registry.resolve(connector_type="tds", provider_name="nsdl_production")
            health = conn.health() if conn and hasattr(conn, "health") else {}
            reachable, ping_detail = _http_ping(cfg.nsdl_base_url)
            detail = json.dumps({"health": health, "ping": ping_detail})
        return ConnectorCheckResult(
            connector="tds",
            configured=configured,
            reachable=reachable,
            status="ok" if configured and reachable else ("configured_unreachable" if configured else "not_configured"),
            detail=detail,
            provider="nsdl_production",
        )

    def check_bank(self) -> ConnectorCheckResult:
        base_url = os.getenv("BANK_API_BASE_URL", "").strip()
        api_key = os.getenv("BANK_API_KEY", "").strip()
        configured = bool(base_url and api_key)
        reachable = False
        detail = "not_configured"
        if configured:
            conn = connector_registry.resolve(connector_type="bank", provider_name="http_bank")
            health = conn.health() if conn and hasattr(conn, "health") else {}
            reachable, ping_detail = _http_ping(base_url)
            detail = json.dumps({"health": health, "ping": ping_detail})
        return ConnectorCheckResult(
            connector="bank",
            configured=configured,
            reachable=reachable,
            status="ok" if configured and reachable else ("configured_unreachable" if configured else "not_configured"),
            detail=detail,
            provider="http_bank",
        )

    def validate_env(self) -> dict:
        gst_ok, gst_missing = _required_env(
            ["GSTN_BASE_URL", "GSTN_API_KEY"]
        ) if not (os.getenv("GSTN_USERNAME") and os.getenv("GSTN_PASSWORD")) else _required_env(
            ["GSTN_BASE_URL", "GSTN_USERNAME", "GSTN_PASSWORD"]
        )
        tds_ok, tds_missing = _required_env(
            ["NSDL_TDS_BASE_URL", "NSDL_TDS_TAN", "NSDL_TDS_USER", "NSDL_TDS_PASSWORD"]
        )
        bank_ok, bank_missing = _required_env(["BANK_API_BASE_URL", "BANK_API_KEY"])
        return {
            "integrations_mode": settings.integrations_mode,
            "gst": {"ok": gst_ok, "missing": gst_missing},
            "tds": {"ok": tds_ok, "missing": tds_missing},
            "bank": {"ok": bank_ok, "missing": bank_missing},
        }

    def run_all(self, *, require_reachable: bool = True) -> dict:
        env = self.validate_env()
        checks = [self.check_gst(), self.check_tds(), self.check_bank()]
        if settings.integrations_use_stubs():
            return {
                "mode": "stub",
                "env": env,
                "checks": [c.__dict__ for c in checks],
                "passed": True,
                "note": "INTEGRATIONS_MODE allows stubs — production UAT skipped",
            }
        passed = all(
            c.configured and (c.reachable or not require_reachable)
            for c in checks
        )
        return {
            "mode": "production",
            "env": env,
            "checks": [c.__dict__ for c in checks],
            "passed": passed,
        }


connector_uat_service = ConnectorUatService()
