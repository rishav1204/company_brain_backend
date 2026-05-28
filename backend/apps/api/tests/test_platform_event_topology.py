from app.modules.platform.events.bus.topology import route_platform_event
from app.services.event_topology import route_for_event_type


def test_erp_invoice_routes_to_workflow_execution() -> None:
    assert route_platform_event("erp.invoice.created").endswith("workflow.execution")
    assert route_for_event_type("erp.invoice.created").endswith("workflow.execution")


def test_workflow_advance_routes_to_approvals() -> None:
    assert route_platform_event("workflow.advance.requested").endswith("workflow.approvals")


def test_ai_ocr_routing() -> None:
    assert route_platform_event("ai.ocr.requested").endswith("ai.ocr")


def test_integration_bank_routing() -> None:
    assert route_platform_event("bank.statement.imported").endswith("integration.bank")
