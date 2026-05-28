def test_event_registry_has_gl_events() -> None:
    from app.modules.platform.events.bus.event_registry import get_event_definition

    assert get_event_definition("erp.ledger.posted") is not None
    assert get_event_definition("erp.ledger.reversed") is not None
    assert get_event_definition("erp.fiscal_period.closed") is not None
    assert get_event_definition("erp.trial_balance.generated") is not None


def test_routers_importable() -> None:
    # Import routers to ensure module wiring doesn't cause circular imports.
    from app.modules.erp.gl.routes.router import erp_gl_router  # noqa: F401
    from app.modules.erp.coa.routes.router import erp_coa_router  # noqa: F401
    from app.modules.platform.documents.routes.router import documents_router  # noqa: F401
    from app.modules.platform.integrations.routes.router import integrations_router  # noqa: F401
    from app.modules.workflows.routes.router import router as workflows_router  # noqa: F401

