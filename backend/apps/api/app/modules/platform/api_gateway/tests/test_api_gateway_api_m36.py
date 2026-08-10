from __future__ import annotations

from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_BACKEND = Path(__file__).resolve().parents[7]
_DOCS = Path(__file__).resolve().parents[8] / "docs"


def test_api_gateway_router_prefix() -> None:
    text = _PKG.joinpath("routes", "router.py").read_text(encoding="utf-8")
    assert 'prefix="/platform"' in text


def test_create_api_key_route_definition() -> None:
    text = _PKG.joinpath("routes", "api_keys_routes.py").read_text(encoding="utf-8")
    assert "api.key.create" in text
    assert "api_key_service.create" in text


def test_list_api_keys_route_definition() -> None:
    text = _PKG.joinpath("routes", "api_keys_routes.py").read_text(encoding="utf-8")
    assert "list_api_keys" in text
    assert '"/api-keys"' in text


def test_create_webhook_route_definition() -> None:
    text = _PKG.joinpath("routes", "webhook_routes.py").read_text(encoding="utf-8")
    assert "webhook.subscribe" in text
    assert "webhook_service.create_subscription" in text


def test_event_catalog_route_definition() -> None:
    text = _PKG.joinpath("routes", "event_routes.py").read_text(encoding="utf-8")
    assert "/events/catalog" in text
    assert "list_partner_catalog" in text


def test_integration_health_route_definition() -> None:
    text = _PKG.joinpath("routes", "integration_health_routes.py").read_text(encoding="utf-8")
    assert "/integrations/health" in text
    assert "connector_registry" in text


def test_m36_doc_golden_rule() -> None:
    doc = _DOCS / "ERP_MODULES" / "M36_api_platform.md"
    if not doc.is_file():
        doc = _BACKEND / "ERP_MODULES" / "M36_api_platform.md"
    text = doc.read_text(encoding="utf-8")
    assert "Golden rule" in text
    assert "integrations.api_keys" in text


def test_erp_master_map_m36_done(erp_master_module_map: str) -> None:
    assert "M36" in erp_master_module_map
    assert "Done" in erp_master_module_map


def test_subscription_routes_alias() -> None:
    text = _PKG.joinpath("routes", "subscription_routes.py").read_text(encoding="utf-8")
    assert "webhook_routes" in text


def test_gateway_schema_webhook_request() -> None:
    text = _PKG.joinpath("schemas", "gateway_schema.py").read_text(encoding="utf-8")
    assert "WebhookCreateRequest" in text
    assert "subscribed_events" in text
