"""Control-plane routes require platform.admin (or authenticated boot)."""

from __future__ import annotations

from app.modules.platform.control_plane.routes import control_plane_routes


def test_platform_ops_routes_gated() -> None:
    expected = control_plane_routes._PLATFORM_ADMIN
    platform_paths = [
        r
        for r in control_plane_routes.router.routes
        if getattr(r, "path", "").startswith("/ops/platform")
    ]
    assert platform_paths, "expected platform control-plane ops routes"
    for route in platform_paths:
        dep_calls = [dep.call for dep in route.dependant.dependencies]
        assert expected in dep_calls, f"{route.path} missing platform.admin gate"


def test_tenant_endpoints_exist() -> None:
    paths = {route.path for route in control_plane_routes.router.routes}
    for p in (
        "/me/boot",
        "/support/tickets",
        "/activity",
        "/recycle-bin",
        "/ops/platform/features",
        "/ops/platform/support/tickets",
        "/ops/platform/activity",
        "/ops/platform/recycle-bin",
    ):
        assert p in paths or any(p in x for x in paths), f"missing route {p}"
