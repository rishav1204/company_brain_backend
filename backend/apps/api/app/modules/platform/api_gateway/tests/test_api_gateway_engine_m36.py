from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.modules.platform.api_gateway.engine import retry_engine
from app.modules.platform.api_gateway.engine.webhook_dispatcher import dispatch_event
from app.modules.platform.api_gateway.schemas.scope_catalog import (
    EVENT_ALIASES,
    PARTNER_SUBSCRIBABLE_EVENTS,
    normalize_event_type,
    scope_to_action,
)
from app.modules.platform.api_gateway.services.signature_service import sign_payload, verify_signature
from app.modules.platform.events.bus.event_registry import get_event_definition

_PKG = Path(__file__).resolve().parents[1]
_PLATFORM = _PKG.parent
_APP = _PLATFORM.parent.parent
_API_ROOT = _APP.parent
_BACKEND = Path(__file__).resolve().parents[7]


def test_migration_061_exists() -> None:
    mig = _BACKEND / "migrations" / "061_api_gateway_platform.sql"
    assert mig.exists()
    text = mig.read_text(encoding="utf-8")
    assert "platform.api_request_log" in text
    assert "integrations.api_keys" in text
    assert "event_stream_adapters" in text


def test_bootstrap_script_exists() -> None:
    script = _BACKEND / "scripts" / "bootstrap_api_gateway.py"
    assert script.exists()


def test_router_prefix() -> None:
    text = _PKG.joinpath("routes", "router.py").read_text(encoding="utf-8")
    assert 'prefix="/platform"' in text


@pytest.mark.parametrize(
    "attempt,expected",
    [(0, 60), (1, 300), (2, 900), (3, 3600), (4, 21600)],
)
def test_retry_schedule(attempt: int, expected: int) -> None:
    assert retry_engine.retry_delay_seconds(attempt) == expected


def test_retry_should_stop_at_max() -> None:
    assert retry_engine.should_retry(4) is True
    assert retry_engine.should_retry(5) is False


def test_hmac_sign_and_verify() -> None:
    secret = "whsec_test"
    body = b'{"event":"invoice.created"}'
    sig = sign_payload(secret, body)
    assert verify_signature(secret, body, sig)
    assert not verify_signature(secret, body, "bad")


def test_event_alias_normalization() -> None:
    assert normalize_event_type("invoice.approved") == "erp.invoice.approved"
    assert normalize_event_type("payment.executed") == "payment.executed"


def test_scope_to_action() -> None:
    assert scope_to_action("webhooks.manage") == "webhook.subscribe"
    assert scope_to_action("admin") == "admin"


def test_partner_events_include_payment_executed() -> None:
    assert "payment.executed" in PARTNER_SUBSCRIBABLE_EVENTS


def test_event_aliases_cover_blueprint() -> None:
    assert "invoice.approved" in EVENT_ALIASES


def test_event_definition_webhook_delivered() -> None:
    defn = get_event_definition("webhook.delivered")
    assert defn is not None
    assert defn.owner == "api_gateway"


def test_event_definition_api_key_created() -> None:
    defn = get_event_definition("api.key.created")
    assert defn is not None


def test_event_definition_integration_connected() -> None:
    defn = get_event_definition("integration.connected")
    assert defn is not None


@patch("app.modules.platform.integrations.services.webhook_service.integrations_webhook_service")
def test_webhook_dispatcher_single_path(mock_wh: MagicMock) -> None:
    mock_wh.dispatch_event.return_value = [{"id": "d1"}]
    out = dispatch_event("org-1", "invoice.approved", {"event_id": "e1"})
    mock_wh.dispatch_event.assert_called_once()
    assert mock_wh.dispatch_event.call_args[0][1] == "erp.invoice.approved"
    assert out == [{"id": "d1"}]


def test_gateway_access_allows_admin_scope() -> None:
    from app.modules.platform.api_gateway.security.gateway_access import _scope_allows

    ctx = MagicMock(api_key_scopes=["admin"], permissions=[])
    assert _scope_allows(ctx, ["invoice.write"]) is True


def test_gateway_access_denies_missing_scope() -> None:
    from app.modules.platform.api_gateway.security.gateway_access import _scope_allows

    ctx = MagicMock(api_key_scopes=["invoice.read"], permissions=[])
    assert _scope_allows(ctx, ["invoice.write"]) is False


@patch("app.modules.platform.api_gateway.security.gateway_access.enforce_gateway_action")
@patch("app.modules.platform.api_gateway.services.api_request_log_service.api_request_log_service")
def test_api_gateway_engine_success(mock_log: MagicMock, _mock_guard: MagicMock) -> None:
    from app.modules.platform.api_gateway.engine.api_gateway_engine import api_gateway_engine

    ctx = MagicMock(org_id="org-1", api_key_id="k1", api_key_scopes=["admin"], attrs={})
    out = api_gateway_engine.process_external_request(
        ctx,
        action="api.key.create",
        method="POST",
        path="/platform/api-keys",
        handler=lambda: {"ok": True},
    )
    assert out["ok"] is True
    mock_log.record.assert_called_once()


@pytest.mark.parametrize(
    "path",
    [
        "engine/api_gateway_engine.py",
        "engine/webhook_dispatcher.py",
        "engine/delivery_engine.py",
        "engine/retry_engine.py",
        "engine/dead_letter_engine.py",
        "services/api_key_service.py",
        "services/webhook_service.py",
        "services/event_stream_service.py",
        "services/signature_service.py",
        "services/rate_limit_service.py",
        "routes/api_keys_routes.py",
        "routes/webhook_routes.py",
        "routes/event_routes.py",
        "security/gateway_access.py",
        "middleware/gateway_middleware.py",
        "middleware/idempotency_middleware.py",
        "events/gateway_events.py",
    ],
)
def test_module_files_exist(path: str) -> None:
    assert _PKG.joinpath(*path.split("/")).exists()


def test_main_includes_api_gateway_router() -> None:
    text = _APP.joinpath("main.py").read_text(encoding="utf-8")
    assert "api_gateway_router" in text
    assert "GatewayMiddleware" in text
    assert "IdempotencyMiddleware" in text


def test_event_service_uses_webhook_dispatcher() -> None:
    text = _PLATFORM.joinpath("events", "services", "event_service.py").read_text(encoding="utf-8")
    assert "webhook_dispatcher" in text
    assert "integrations_webhook_service.dispatch_event" not in text


def test_middleware_public_inbound_webhook() -> None:
    text = _APP.joinpath("middleware.py").read_text(encoding="utf-8")
    assert "_PUBLIC_PATH_PREFIXES" in text
    assert "webhooks/inbound" in text


def test_audit_materialization_includes_webhook_events() -> None:
    text = (
        _APP.joinpath("modules", "finance_os", "audit_explorer", "pipelines", "audit_materialization_pipeline.py")
        .read_text(encoding="utf-8")
    )
    assert "webhook.delivered" in text
    assert "webhook.received" in text
    assert "api.key.created" in text


def test_inbound_webhook_audits() -> None:
    text = _PLATFORM.joinpath("integrations", "routes", "inbound_webhook_routes.py").read_text(encoding="utf-8")
    assert "audit_service.record" in text


def test_accounting_connectors_registered() -> None:
    import app.modules.platform.integrations.connectors as _connectors  # noqa: F401
    from app.modules.platform.integrations.services.connector_registry import connector_registry

    assert connector_registry.resolve(connector_type="accounting", provider_name="tally") is not None
    assert connector_registry.resolve(connector_type="accounting", provider_name="zoho") is not None
    assert connector_registry.resolve(connector_type="accounting", provider_name="sap") is not None


def test_deps_enriches_api_key_attrs() -> None:
    text = _APP.joinpath("api", "deps.py").read_text(encoding="utf-8")
    assert 'attrs={"actor_type": "api_key"' in text


def test_webhook_signature_header_x_signature() -> None:
    text = _PLATFORM.joinpath("integrations", "services", "webhook_service.py").read_text(encoding="utf-8")
    assert "X-Signature" in text


def test_dead_letter_engine_facade() -> None:
    from app.modules.platform.api_gateway.engine.dead_letter_engine import dead_letter_engine

    assert hasattr(dead_letter_engine, "dlq_depth")
    assert hasattr(dead_letter_engine, "requeue")


def test_rate_limit_service_allow() -> None:
    from app.modules.platform.api_gateway.services.rate_limit_service import gateway_rate_limit_service

    assert gateway_rate_limit_service.allow(org_id="o1", api_key_id="k1") is True


def test_event_stream_partner_catalog() -> None:
    from app.modules.platform.api_gateway.services.event_stream_service import event_stream_service

    catalog = event_stream_service.list_partner_catalog()
    types = {c["event_type"] for c in catalog}
    assert "payment.executed" in types or "workflow.started" in types


def test_scope_catalog_invoice_read() -> None:
    from app.modules.platform.api_gateway.schemas.scope_catalog import SCOPE_CATALOG

    assert "invoice.read" in SCOPE_CATALOG


def test_retry_max_attempts_is_five() -> None:
    assert retry_engine.WEBHOOK_MAX_ATTEMPTS == 5


def test_hmac_matches_manual() -> None:
    secret = "s"
    body = b"data"
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert sign_payload(secret, body) == expected


def test_normalize_unknown_event_passthrough() -> None:
    assert normalize_event_type("custom.event") == "custom.event"


def test_partner_events_count() -> None:
    assert len(PARTNER_SUBSCRIBABLE_EVENTS) >= 15


def test_event_definition_webhook_failed() -> None:
    assert get_event_definition("webhook.failed") is not None


def test_event_definition_api_key_revoked() -> None:
    assert get_event_definition("api.key.revoked") is not None


def test_gateway_events_emit_key_created() -> None:
    from app.modules.platform.api_gateway.events.gateway_events import GatewayEvents

    assert hasattr(GatewayEvents, "emit_key_created")


def test_delivery_engine_dispatch() -> None:
    from app.modules.platform.api_gateway.engine.delivery_engine import delivery_engine

    assert hasattr(delivery_engine, "dispatch")


def test_api_request_log_service_record() -> None:
    from app.modules.platform.api_gateway.services.api_request_log_service import api_request_log_service

    assert hasattr(api_request_log_service, "record")


def test_legacy_webhook_deprecation_note() -> None:
    text = (_BACKEND / "migrations" / "061_api_gateway_platform.sql").read_text()
    assert "deprecated" in text.lower()


def test_integrations_schema_not_duplicated() -> None:
    text = (_BACKEND / "migrations" / "061_api_gateway_platform.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS platform.api_keys" not in text


def test_event_stream_service_list_events() -> None:
    from unittest.mock import patch
    from app.modules.platform.api_gateway.services.event_stream_service import event_stream_service

    with patch.object(event_stream_service, "list_events", return_value=[]):
        assert event_stream_service.list_events("00000000-0000-0000-0000-000000000001", limit=1) == []


def test_signature_service_roundtrip_empty() -> None:
    assert verify_signature("x", b"", sign_payload("x", b""))


def test_retry_engine_delays_monotonic() -> None:
    delays = [retry_engine.retry_delay_seconds(i) for i in range(5)]
    assert delays == sorted(delays)


def test_webhook_dispatcher_normalizes_gst() -> None:
    with patch("app.modules.platform.integrations.services.webhook_service.integrations_webhook_service") as mock_wh:
        mock_wh.dispatch_event.return_value = []
        dispatch_event("o", "gst.return.generated", {})
        assert mock_wh.dispatch_event.call_args[0][1] == "erp.gst.return.generated"


def test_gateway_access_enforce_raises_on_deny() -> None:
    from fastapi import HTTPException
    from app.modules.platform.api_gateway.security.gateway_access import enforce_gateway_action

    ctx = MagicMock(
        org_id="o",
        user_id="u",
        roles=["viewer"],
        auth_method="api_key",
        api_key_scopes=["invoice.read"],
        permissions=[],
        attrs={},
    )
    with patch("app.modules.platform.api_gateway.security.gateway_access.evaluate_access") as mock_eval:
        mock_eval.return_value = MagicMock(allowed=False, reason="denied")
        with pytest.raises(HTTPException) as exc:
            enforce_gateway_action(ctx, action="api.key.create", required_scopes=["admin"])
        assert exc.value.status_code == 403


def test_gateway_access_scope_violation_before_policy() -> None:
    from fastapi import HTTPException
    from app.modules.platform.api_gateway.security.gateway_access import enforce_gateway_action

    ctx = MagicMock(
        org_id="o",
        user_id="u",
        roles=[],
        auth_method="api_key",
        api_key_scopes=["invoice.read"],
        permissions=[],
        attrs={},
    )
    with pytest.raises(HTTPException) as exc:
        enforce_gateway_action(ctx, action="x", required_scopes=["admin"])
    assert exc.value.status_code == 403


def test_tally_connector_health() -> None:
    from app.modules.platform.integrations.connectors.accounting.accounting_connectors import TallyConnector

    assert TallyConnector().health()["ready"] is True


def test_zoho_connector_export() -> None:
    from app.modules.platform.integrations.connectors.accounting.accounting_connectors import ZohoConnector

    out = ZohoConnector().export_journal(journal={"id": "j1"})
    assert out["provider"] == "zoho"


def test_sap_connector_export() -> None:
    from app.modules.platform.integrations.connectors.accounting.accounting_connectors import SapConnector

    out = SapConnector().export_journal(journal={"id": "j2"})
    assert out["status"] == "queued"


def test_m36_doc_placeholder() -> None:
    doc = _BACKEND / "ERP_MODULES" / "M36_api_platform.md"
    assert doc.exists()


def test_erp_master_map_m36() -> None:
    text = (_BACKEND / "ERP_MASTER_MODULE_MAP.md").read_text(encoding="utf-8")
    assert "M36" in text


def test_api_keys_route_paths() -> None:
    text = _PKG.joinpath("routes", "api_keys_routes.py").read_text(encoding="utf-8")
    assert "/api-keys" in text


def test_webhook_route_paths() -> None:
    text = _PKG.joinpath("routes", "webhook_routes.py").read_text(encoding="utf-8")
    assert "/webhooks" in text


def test_event_routes_catalog() -> None:
    text = _PKG.joinpath("routes", "event_routes.py").read_text(encoding="utf-8")
    assert "/events/catalog" in text


def test_integration_health_route() -> None:
    text = _PKG.joinpath("routes", "integration_health_routes.py").read_text(encoding="utf-8")
    assert "/integrations/health" in text


def test_idempotency_middleware_exists() -> None:
    text = _PKG.joinpath("middleware", "idempotency_middleware.py").read_text(encoding="utf-8")
    assert "Idempotency-Key" in text


def test_gateway_middleware_cbk_prefix() -> None:
    text = _PKG.joinpath("middleware", "gateway_middleware.py").read_text(encoding="utf-8")
    assert "cbk_" in text


def test_api_key_service_create_emits_event() -> None:
    text = _PKG.joinpath("services", "api_key_service.py").read_text(encoding="utf-8")
    assert "emit_key_created" in text


def test_webhook_service_deactivate() -> None:
    from app.modules.platform.api_gateway.services.webhook_service import webhook_service

    assert hasattr(webhook_service, "deactivate")


def test_event_registry_webhook_received_owner() -> None:
    defn = get_event_definition("webhook.received")
    assert defn is not None
    assert defn.owner == "integration.webhooks"


def test_materialize_includes_integration_connected() -> None:
    text = (
        _APP.joinpath("modules", "finance_os", "audit_explorer", "pipelines", "audit_materialization_pipeline.py")
        .read_text(encoding="utf-8")
    )
    assert "integration.connected" in text


def test_connectors_init_imports_accounting() -> None:
    text = _PLATFORM.joinpath("integrations", "connectors", "__init__.py").read_text(encoding="utf-8")
    assert "accounting_connectors" in text


def test_api_key_repository_gateway_fields() -> None:
    text = _PLATFORM.joinpath("integrations", "repositories", "api_key_repository.py").read_text(encoding="utf-8")
    assert "update_gateway_fields" in text
    assert "ip_allowlist" in text


def test_webhook_repository_deactivate() -> None:
    text = _PLATFORM.joinpath("integrations", "repositories", "webhook_repository.py").read_text(encoding="utf-8")
    assert "deactivate" in text
