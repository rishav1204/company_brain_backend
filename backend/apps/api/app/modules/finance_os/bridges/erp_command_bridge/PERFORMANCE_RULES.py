"""Performance / structural rules for the Command Bridge (enforced by tests)."""

from __future__ import annotations

# Bridge package MUST remain:
BRIDGE_RULES = (
    "no_business_logic",
    "no_sql",
    "no_repository_imports",
    "stateless_process_local_registry_only",
    "delegates_mutations_via_allowlist",
)

FORBIDDEN_IMPORT_PREFIXES_IN_BRIDGE_CORE = (
    "app.modules.erp.accounts_payable.repositories",
    "app.modules.erp.journals.repositories",
    "app.modules.erp.gl.repositories",
)

# Services under bridge may import dispatch only via handlers; not domain repos
BRIDGE_CORE_PACKAGES = (
    "contracts",
    "validators",
    "authorization",
    "approval",
    "events",
    "registry",
    "idempotency",
    "retry",
    "observability",
    "services",
)
