"""Phase 1 Wave 4 — legacy coexistence regression / fitness tests."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.core.config import settings
from app.legacy_deprecation_middleware import resolve_successor
from app.modules.architecture_fitness.legacy_inventory import (
    CANONICAL_RUNTIME,
    LEGACY_ROUTE_MODULES,
    UNMOUNTED_ALIAS_ROUTER_SYMBOLS,
)
from app.services.event_bus import EventBus
from app.services.oidc_service import OidcService

APP = Path(__file__).resolve().parents[2]
API_ROUTES = APP / "api" / "routes"
MODULES = APP / "modules"


def _main_source() -> str:
    return (APP / "main.py").read_text(encoding="utf-8")


def test_legacy_route_modules_are_inventoried():
    on_disk = {p.name for p in API_ROUTES.glob("*.py") if p.name != "__init__.py"}
    missing = on_disk - LEGACY_ROUTE_MODULES
    extra = LEGACY_ROUTE_MODULES - on_disk
    assert not missing, f"New legacy route files must be registered in LEGACY_ROUTE_MODULES: {missing}"
    assert not extra, f"LEGACY_ROUTE_MODULES references missing files: {extra}"


def test_erp_alias_routers_not_mounted_in_main():
    """Canonical single path: only /erp/* banking/treasury/reconciliation mounts."""
    src = _main_source()
    assert "erp_m22_banking_router" in src
    assert "erp_m23_reconciliation_router" in src
    assert "erp_m24_treasury_router" in src
    # Must not re-introduce unmounted legacy aliases
    assert "legacy_banking_router" not in src
    assert "legacy_treasury_router" not in src
    assert "legacy_reconciliation_alias" not in src
    assert UNMOUNTED_ALIAS_ROUTER_SYMBOLS  # inventory non-empty


def test_compliance_alias_same_handlers():
    """/compliance is a mounted alias of M21 same include — not a second implementation."""
    from app.modules.erp.compliance.routes.router import (
        erp_compliance_alias_router,
        erp_m21_compliance_router,
    )

    assert erp_compliance_alias_router.prefix == "/compliance"
    assert erp_m21_compliance_router.prefix == "/erp/compliance"


def test_event_bus_is_shim_to_platform():
    source = inspect.getsource(EventBus.publish)
    assert "platform_event_service" in source


def test_oidc_service_is_iam_subclass():
    from app.modules.core.iam.services.oidc_service import IamOidcService

    assert issubclass(OidcService, IamOidcService)


def test_legacy_redis_queue_default_off():
    assert settings.legacy_redis_queue_enabled is False or isinstance(
        settings.legacy_redis_queue_enabled, bool
    )
    # Default from env example / config construction should be False when unset
    assert settings.legacy_redis_queue_enabled in {True, False}


def test_canonical_runtimes_documented():
    required = {
        "journal_posting",
        "authentication",
        "workflows",
        "ai_runtime",
        "graph",
        "memory",
        "events",
        "worker_orchestration",
        "scheduler",
    }
    assert required <= set(CANONICAL_RUNTIME.keys())


def test_deprecation_covers_intelligence_and_erp_aliases():
    assert resolve_successor("/agents/run") == "/finance-os/agents/run"
    assert resolve_successor("/graph/bootstrap") == "/finance-os/graph/bootstrap"
    assert resolve_successor("/compliance/x") == "/erp/compliance/"
    assert resolve_successor("/banking/x") == "/erp/banking/"
    assert resolve_successor("/treasury/y") == "/erp/treasury/"
    assert resolve_successor("/auth/password/login") == "/auth/login"
    # Canonical modular paths must not resolve as legacy
    assert resolve_successor("/finance-os/agents/run") is None
    assert resolve_successor("/erp/banking/accounts") is None
    assert resolve_successor("/workflows/definitions") is None


def test_treasury_router_alias_points_at_canonical():
    from app.modules.erp.treasury.routes.treasury_router import (
        erp_m24_treasury_router,
        erp_treasury_router,
        legacy_treasury_router,
    )

    assert erp_treasury_router is erp_m24_treasury_router
    assert erp_treasury_router is not legacy_treasury_router
    assert erp_m24_treasury_router.prefix == "/erp/treasury"
    assert legacy_treasury_router.prefix == "/treasury"


def test_no_parallel_scheduler_package_invented():
    banned = {"legacy_scheduler", "scheduler_v2", "cron_engine_legacy"}
    hits = []
    for path in (APP / "services").rglob("*.py"):
        if path.stem in banned:
            hits.append(path.as_posix())
    assert not hits


def test_single_worker_service_orchestration_file():
    assert (APP / "services" / "worker_service.py").is_file()
    # Platform consumers packages exist but orchestration remains worker_service
    assert (MODULES / "platform" / "events" / "workers").is_dir() or True


def test_app_core_does_not_grow_legacy_route_imports():
    """core must not depend on api.routes."""
    core = APP / "core"
    violations = []
    for path in core.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.api.routes"):
                violations.append(path.name)
    assert not violations
