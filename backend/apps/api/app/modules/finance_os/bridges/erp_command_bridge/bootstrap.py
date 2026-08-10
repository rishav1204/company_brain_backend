"""Wire command registry, query registry, allowlists, intelligence ports. Idempotent."""

from __future__ import annotations

_BOOTSTRAPPED = False


def bootstrap_wave1_boundaries() -> None:
    global _BOOTSTRAPPED
    # Safe to re-run; registry register overwrites same keys.

    # --- Bootstrap order (documented) ---
    # 1. Mutation allowlist + Command Registry (ERP write contracts)
    # 2. Query Registry + read allowlist (ERP read contracts)
    # 3. Intelligence port adapters (ERP → FOS runtime)
    # 4. Ready for API / workers / AI runtime

    from app.modules.finance_os.bridges.erp_command_bridge.handlers.erp_dispatch import register_mutation_target
    from app.modules.finance_os.bridges.erp_command_bridge.registry.command_registry import (
        CommandRegistration,
        command_registry,
    )
    from app.modules.finance_os.platform_ai_runtime.tools.catalog_draft import DRAFT_SPECS

    for spec in DRAFT_SPECS:
        if not str(spec.module).startswith("app.modules.erp."):
            continue
        name = f"{spec.tool}.{spec.method}"
        command_registry.register(
            CommandRegistration(
                name=name,
                erp_module=spec.module,
                erp_service=spec.service,
                erp_fn=spec.fn,
                policy_action=spec.policy_action or name,
                requires_approval=bool(spec.requires_approval),
                org_style=getattr(spec, "org_style", "first") or "first",
                max_attempts=1,
                idempotent=True,
                description=f"M38 draft tool {name}",
                required_payload_keys=tuple(spec.required or ()),
                tags=("m38", "draft", spec.tool),
            ),
            tool=spec.tool,
            method=spec.method,
        )

    command_registry.register(
        CommandRegistration(
            name="CreateVoucherFromExtraction",
            erp_module="app.modules.erp.vouchers.services.voucher_service",
            erp_service="voucher_service",
            erp_fn="create_from_extraction",
            policy_action="vouchers.create_from_extraction",
            requires_approval=False,
            max_attempts=1,
            idempotent=True,
            description="Invoice AI auto-draft voucher from extraction",
            required_payload_keys=("extraction_id",),
            tags=("invoice_ai", "vouchers"),
        ),
        tool="vouchers",
        method="create_from_extraction",
    )
    # Keep allowlist for any residual direct triples
    register_mutation_target(
        "app.modules.erp.vouchers.services.voucher_service",
        "voucher_service",
        "create_from_extraction",
    )

    # --- Query registry ---
    from app.modules.erp.query_services.registry import QueryRegistration, query_registry
    from app.modules.erp.query_services.dispatch import ap_queries, ar_queries, compliance_queries
    from app.modules.erp.query_services.dispatch import (
        fiscal_queries,
        inventory_queries,
        reconciliation_queries,
        reporting_queries,
        treasury_queries,
    )
    from app.modules.finance_os.platform_ai_runtime.tools.catalog_read import READ_SPECS

    # Catalog reads
    for spec in READ_SPECS:
        if not str(spec.module).startswith("app.modules.erp."):
            continue
        qname = f"{spec.tool}.{spec.method}"
        query_registry.register(
            QueryRegistration(
                name=qname,
                description=f"M38 read tool {qname}",
                erp_module=spec.module,
                erp_service=spec.service,
                erp_fn=spec.fn,
                org_style=getattr(spec, "org_style", "first") or "first",
                tags=("m38", "read", spec.tool),
            )
        )

    # Canonical named queries for Finance OS product code
    named = [
        QueryRegistration(
            name="GetVendorByGstin",
            description="Lookup vendor by GSTIN",
            handler=lambda org_id, **kw: ap_queries.find_vendor_by_gstin(org_id, **kw),
            tags=("ap", "vendor"),
        ),
        QueryRegistration(
            name="ListApInvoices",
            description="List AP invoices",
            handler=lambda org_id, **kw: ap_queries.list_invoices(org_id, **kw),
            tags=("ap", "invoice"),
        ),
        QueryRegistration(
            name="ListOutstandingAp",
            description="Outstanding AP invoices",
            handler=lambda org_id, **kw: ap_queries.list_outstanding_invoices(org_id),
            tags=("ap", "invoice"),
        ),
        QueryRegistration(
            name="ListOutstandingAr",
            description="Outstanding AR invoices",
            handler=lambda org_id, **kw: ar_queries.list_outstanding_invoices(org_id),
            tags=("ar", "invoice"),
        ),
        QueryRegistration(
            name="GetCashPosition",
            description="Live cash position",
            handler=lambda org_id, **kw: treasury_queries.compute_live_position(org_id),
            tags=("treasury", "cash"),
        ),
        QueryRegistration(
            name="GetApAging",
            description="AP aging report",
            handler=lambda org_id, **kw: reporting_queries.get_ap_aging(org_id, **kw),
            tags=("reporting", "ap"),
        ),
        QueryRegistration(
            name="GetArAging",
            description="AR aging report",
            handler=lambda org_id, **kw: reporting_queries.get_ar_aging(org_id, **kw),
            tags=("reporting", "ar"),
        ),
        QueryRegistration(
            name="GetPnl",
            description="P&L report",
            handler=lambda org_id, **kw: reporting_queries.get_pnl(org_id, **kw),
            tags=("reporting", "pnl"),
        ),
        QueryRegistration(
            name="GetFiscalPeriod",
            description="Fiscal period by id",
            handler=lambda org_id, **kw: fiscal_queries.get_period(org_id, **kw),
            tags=("fiscal",),
        ),
        QueryRegistration(
            name="GetItemByCode",
            description="Inventory item by code",
            handler=lambda org_id, **kw: inventory_queries.get_item_by_code(org_id, **kw),
            tags=("inventory",),
        ),
        QueryRegistration(
            name="GetComplianceDashboard",
            description="Compliance dashboard",
            handler=lambda org_id, **kw: compliance_queries.dashboard(org_id, **kw),
            tags=("compliance",),
        ),
        QueryRegistration(
            name="RunReconciliationScan",
            description="Reconciliation scan (side-effecting job exposed as query for analytics)",
            handler=lambda org_id, **kw: reconciliation_queries.run_scan(org_id, **kw),
            tags=("reconciliation", "side_effect"),
        ),
    ]
    for reg in named:
        query_registry.register(reg)

    # --- Intelligence ports ---
    from app.modules.erp.ports.intelligence_registry import intelligence_registry
    from app.modules.finance_os.bridges.erp_command_bridge.adapters.forecast_intelligence_adapter import (
        ForecastIntelligenceAdapter,
    )
    from app.modules.finance_os.bridges.erp_command_bridge.adapters.invoice_intelligence_adapter import (
        InvoiceIntelligenceAdapter,
    )

    from app.modules.finance_os.bridges.erp_command_bridge.adapters.ap_intelligence_adapter import (
        ApRiskIntelligenceAdapter,
    )
    from app.modules.finance_os.bridges.erp_command_bridge.adapters.expense_intelligence_adapter import (
        ExpenseIntelligenceAdapter,
    )
    from app.modules.finance_os.bridges.erp_command_bridge.adapters.journal_intelligence_adapter import (
        JournalIntelligenceAdapter,
    )

    intelligence_registry.register_invoice(InvoiceIntelligenceAdapter(), version="v1")
    intelligence_registry.register_forecast(ForecastIntelligenceAdapter(), version="v1")
    intelligence_registry.register("ap_risk", ApRiskIntelligenceAdapter(), version="v1")
    intelligence_registry.register("expense", ExpenseIntelligenceAdapter(), version="v1")
    intelligence_registry.register("journal", JournalIntelligenceAdapter(), version="v1")

    from app.modules.finance_os.bridges.erp_command_bridge.adapters.ar_intelligence_adapter import (
        ArCollectionsIntelligenceAdapter,
    )
    from app.modules.finance_os.bridges.erp_command_bridge.adapters.banking_intelligence_adapter import (
        BankingIntelligenceAdapter,
    )
    from app.modules.finance_os.bridges.erp_command_bridge.adapters.reconciliation_intelligence_adapter import (
        ReconciliationIntelligenceAdapter,
    )
    from app.modules.finance_os.bridges.erp_command_bridge.adapters.treasury_intelligence_adapter import (
        TreasuryIntelligenceAdapter,
    )

    intelligence_registry.register("ar_collections", ArCollectionsIntelligenceAdapter(), version="v1")
    intelligence_registry.register("banking", BankingIntelligenceAdapter(), version="v1")
    intelligence_registry.register("treasury", TreasuryIntelligenceAdapter(), version="v1")
    intelligence_registry.register("reconciliation", ReconciliationIntelligenceAdapter(), version="v1")

    from app.modules.finance_os.bridges.erp_command_bridge.adapters.compliance_intelligence_adapter import (
        ComplianceIntelligenceAdapter,
    )
    from app.modules.finance_os.bridges.erp_command_bridge.adapters.tax_intelligence_adapter import (
        TaxIntelligenceAdapter,
    )

    intelligence_registry.register("tax", TaxIntelligenceAdapter(), version="v1")
    intelligence_registry.register("compliance", ComplianceIntelligenceAdapter(), version="v1")

    from app.modules.finance_os.bridges.erp_command_bridge.adapters.ops_intelligence_adapters import (
        AssetIntelligenceAdapter,
        InventoryIntelligenceAdapter,
        ProcurementIntelligenceAdapter,
    )

    intelligence_registry.register("procurement", ProcurementIntelligenceAdapter(), version="v1")
    intelligence_registry.register("inventory", InventoryIntelligenceAdapter(), version="v1")
    intelligence_registry.register("asset", AssetIntelligenceAdapter(), version="v1")

    _BOOTSTRAPPED = True


def is_bootstrapped() -> bool:
    return _BOOTSTRAPPED
