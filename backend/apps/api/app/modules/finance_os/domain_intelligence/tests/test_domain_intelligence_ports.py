"""Port registration + ACL smoke tests for the ERP → Finance OS intelligence migration."""

from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import PORT_NAMES, intelligence_registry
from app.modules.finance_os.bridges.erp_command_bridge.bootstrap import bootstrap_wave1_boundaries


def test_all_domain_ports_registered_after_bootstrap() -> None:
    bootstrap_wave1_boundaries()
    missing = [name for name in PORT_NAMES if not intelligence_registry.is_registered(name)]
    assert not missing, f"intelligence ports not registered: {missing}"


def test_describe_reports_every_port() -> None:
    bootstrap_wave1_boundaries()
    described = intelligence_registry.describe()
    assert set(described) == set(PORT_NAMES)
    assert described["invoice"]["registered"] is True
    assert intelligence_registry.invoice_version() == "v1"
    assert intelligence_registry.forecast_version() == "v1"


def test_domain_calc_acl_exposes_erp_math() -> None:
    from app.modules.erp.query_services import domain_calc

    assert domain_calc.ap_aging_days(due_date="2026-01-01", as_of="2026-01-31") == 30
    assert domain_calc.compute_discount(invoice_amount=1000, discount_rate=0.02) == 20.0
    assert domain_calc.gstin_error("not-a-gstin")
    assert domain_calc.gstin_error("27AAPFU0939F1ZV") is None


def test_fallback_used_when_port_raises() -> None:
    from app.modules.erp.ports.intelligence_registry import IntelligenceRegistry

    class Boom:
        def analyze(self, org_id: str, *, query: str) -> dict:
            raise RuntimeError("down")

    registry = IntelligenceRegistry()
    registry.register(
        "inventory",
        Boom(),
        fallback=lambda *a, **k: {"degraded": True},
    )
    assert registry.invoke("inventory", "analyze", "org", query="x") == {"degraded": True}
