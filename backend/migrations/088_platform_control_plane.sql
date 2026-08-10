-- Platform control plane: feature catalog, screens, org/user controls,
-- support tickets, activity feed, recycle bin.

CREATE SCHEMA IF NOT EXISTS platform;
CREATE SCHEMA IF NOT EXISTS support;

-- ---------------------------------------------------------------------------
-- Feature catalog (source of truth for feature_code rows)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform.feature_catalog (
    feature_code VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    category VARCHAR(32) NOT NULL DEFAULT 'erp',
    is_ai BOOLEAN NOT NULL DEFAULT FALSE,
    parent_code VARCHAR(64) NULL REFERENCES platform.feature_catalog(feature_code) ON DELETE SET NULL,
    depends_on JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_level SMALLINT NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO platform.feature_catalog (feature_code, name, category, is_ai) VALUES
    ('coa', 'Chart of accounts', 'erp', FALSE),
    ('gl', 'General ledger', 'erp', FALSE),
    ('journals', 'Journals', 'erp', FALSE),
    ('vouchers', 'Vouchers', 'erp', FALSE),
    ('ap', 'Accounts payable', 'erp', FALSE),
    ('ar', 'Accounts receivable', 'erp', FALSE),
    ('gst', 'GST', 'erp', FALSE),
    ('tds', 'TDS', 'erp', FALSE),
    ('compliance', 'Compliance', 'erp', FALSE),
    ('banking', 'Banking', 'erp', FALSE),
    ('reporting', 'Reporting', 'reporting', FALSE),
    ('procurement', 'Procurement', 'erp', FALSE),
    ('expense', 'Expenses', 'erp', FALSE),
    ('assets', 'Fixed assets', 'erp', FALSE),
    ('reconciliation', 'Reconciliation', 'erp', FALSE),
    ('treasury', 'Treasury', 'erp', FALSE),
    ('analytics', 'Analytics', 'reporting', FALSE),
    ('audit_explorer', 'Audit explorer', 'reporting', FALSE),
    ('invoice_ai', 'Invoice AI', 'ai', TRUE),
    ('workflow_intelligence', 'Workflow intelligence', 'ai', TRUE),
    ('memory', 'Memory engine', 'ai', TRUE),
    ('graph_engine', 'Knowledge graph', 'ai', TRUE),
    ('agents', 'AI agents & copilot', 'ai', TRUE),
    ('forecasting', 'Forecasting', 'ai', TRUE),
    ('api_platform', 'API platform', 'platform', FALSE),
    ('consolidation', 'Consolidation', 'erp', FALSE),
    ('multi_entity', 'Multi-entity', 'erp', FALSE),
    ('inventory', 'Inventory', 'erp', FALSE)
ON CONFLICT (feature_code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- UI screen registry
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform.ui_screen_registry (
    screen_key VARCHAR(128) PRIMARY KEY,
    route_path VARCHAR(512) NOT NULL,
    label VARCHAR(255) NOT NULL,
    nav_category VARCHAR(64) NULL,
    feature_code VARCHAR(64) NULL REFERENCES platform.feature_catalog(feature_code) ON DELETE SET NULL,
    permission_key VARCHAR(128) NULL,
    console VARCHAR(16) NOT NULL DEFAULT 'erp',
    sort_order INT NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS platform_ui_screen_route_idx ON platform.ui_screen_registry (route_path);

-- Seed screens from FE NAV_CONFIG + platform owner console (idempotent upsert)
-- Seed screens from FE NAV_CONFIG + platform owner console (idempotent upsert)
-- Seed screens from FE NAV_CONFIG + platform owner console (idempotent upsert)
INSERT INTO platform.ui_screen_registry
    (screen_key, route_path, label, nav_category, feature_code, permission_key, console, sort_order)
VALUES
    ('erp.dashboard', '/dashboard', 'Dashboard', 'Finance', NULL, 'analytics.read', 'erp', 10),
    ('erp.notifications', '/notifications', 'Notifications', 'Finance', NULL, 'notification.read', 'erp', 20),
    ('erp.workflows', '/workflows', 'Workflows', 'Finance', NULL, 'workflow.read', 'erp', 30),
    ('erp.workflows.approvals', '/workflows/approvals', 'Approvals', 'Finance', NULL, 'approval.read', 'erp', 40),
    ('erp.workflows.tasks', '/workflows/tasks', 'Tasks', 'Finance', NULL, 'task.read', 'erp', 50),
    ('erp.workflows.escalations', '/workflows/escalations', 'Escalations', 'Finance', NULL, 'workflow.read', 'erp', 60),
    ('erp.workflows.definitions', '/workflows/definitions', 'Definitions', 'Finance', NULL, 'workflow.manage', 'erp', 70),
    ('erp.accounting.coa', '/accounting/coa', 'Chart of accounts', 'Accounting', 'coa', 'coa.read', 'erp', 80),
    ('erp.accounting.journals', '/accounting/journals', 'Journals', 'Accounting', 'journals', 'journal.read', 'erp', 90),
    ('erp.accounting.journals.approval_queue', '/accounting/journals/approval-queue', 'Journal approvals', 'Accounting', 'journals', 'journal.approve', 'erp', 100),
    ('erp.accounting.gl.ledger', '/accounting/gl/ledger', 'Ledger', 'Accounting', 'gl', 'gl.read', 'erp', 110),
    ('erp.accounting.gl.trial_balance', '/accounting/gl/trial-balance', 'Trial balance', 'Accounting', 'gl', 'gl.read', 'erp', 120),
    ('erp.accounting.vouchers', '/accounting/vouchers', 'Vouchers', 'Accounting', 'vouchers', 'voucher.read', 'erp', 130),
    ('erp.accounting.fiscal.years', '/accounting/fiscal/years', 'Fiscal years', 'Accounting', 'gl', 'gl.read', 'erp', 140),
    ('erp.accounting.fiscal.periods', '/accounting/fiscal/periods', 'Fiscal periods', 'Accounting', 'gl', 'gl.read', 'erp', 150),
    ('erp.accounting.fiscal.year_end', '/accounting/fiscal/year-end', 'Year-end', 'Accounting', 'gl', 'gl.read', 'erp', 160),
    ('erp.operations.assets.register', '/operations/assets/register', 'Asset register', 'Operations', 'assets', 'asset.read', 'erp', 170),
    ('erp.operations.assets.candidates', '/operations/assets/candidates', 'Capitalization candidates', 'Operations', 'assets', 'asset.read', 'erp', 180),
    ('erp.operations.inventory.summary', '/operations/inventory/summary', 'Stock summary', 'Operations', 'inventory', 'inventory.read', 'erp', 190),
    ('erp.operations.inventory.items', '/operations/inventory/items', 'Inventory items', 'Operations', 'inventory', 'inventory.read', 'erp', 200),
    ('erp.operations.inventory.movements', '/operations/inventory/movements', 'Stock movements', 'Operations', 'inventory', 'inventory.read', 'erp', 210),
    ('erp.documents', '/documents', 'Documents', 'Finance', NULL, 'document.read', 'erp', 220),
    ('erp.operations.ap.vendors', '/operations/ap/vendors', 'Vendors', 'Operations', 'ap', 'ap.vendor.read', 'erp', 230),
    ('erp.operations.ap.invoices', '/operations/ap/invoices', 'Invoices', 'Operations', 'ap', 'ap.invoice.read', 'erp', 240),
    ('erp.operations.ap.payments', '/operations/ap/payments', 'AP payments', 'Operations', 'ap', 'ap.payment.read', 'erp', 250),
    ('erp.operations.ap.aging', '/operations/ap/aging', 'AP aging', 'Operations', 'ap', 'ap.invoice.read', 'erp', 260),
    ('erp.operations.ar.customers', '/operations/ar/customers', 'Customers', 'Operations', 'ar', 'ar.customer.read', 'erp', 270),
    ('erp.operations.ar.invoices', '/operations/ar/invoices', 'AR invoices', 'Operations', 'ar', 'ar.invoice.read', 'erp', 280),
    ('erp.operations.ar.collections', '/operations/ar/collections', 'Collections', 'Operations', 'ar', 'ar.collection.manage', 'erp', 290),
    ('erp.operations.ar.aging', '/operations/ar/aging', 'AR aging', 'Operations', 'ar', 'ar.invoice.read', 'erp', 300),
    ('erp.operations.procurement.pr', '/operations/procurement/pr', 'Requisitions', 'Operations', 'procurement', 'procurement.read', 'erp', 310),
    ('erp.operations.procurement.po', '/operations/procurement/po', 'Purchase orders', 'Operations', 'procurement', 'procurement.read', 'erp', 320),
    ('erp.operations.procurement.grn', '/operations/procurement/grn', 'GRN', 'Operations', 'procurement', 'procurement.read', 'erp', 330),
    ('erp.operations.procurement.matches', '/operations/procurement/matches', '3-way match', 'Operations', 'procurement', 'procurement.read', 'erp', 340),
    ('erp.operations.procurement.analytics', '/operations/procurement/analytics', 'Spend analytics', 'Operations', 'procurement', 'procurement.read', 'erp', 350),
    ('erp.operations.expenses.claims', '/operations/expenses/claims', 'Expense claims', 'Operations', 'expense', 'expense.read', 'erp', 360),
    ('erp.operations.expenses.advances', '/operations/expenses/advances', 'Expense advances', 'Operations', 'expense', 'expense.read', 'erp', 370),
    ('erp.operations.expenses.policies', '/operations/expenses/policies', 'Expense policies', 'Operations', 'expense', 'expense.read', 'erp', 380),
    ('erp.operations.expenses.analytics', '/operations/expenses/analytics', 'Expense analytics', 'Operations', 'expense', 'expense.read', 'erp', 390),
    ('erp.compliance.gst', '/compliance/gst', 'GST overview', 'Compliance', 'gst', 'tax.read', 'erp', 400),
    ('erp.compliance.gst.registrations', '/compliance/gst/registrations', 'GST registrations', 'Compliance', 'gst', 'tax.read', 'erp', 410),
    ('erp.compliance.gst.itc', '/compliance/gst/itc', 'GST ITC', 'Compliance', 'gst', 'tax.read', 'erp', 420),
    ('erp.compliance.gst.returns', '/compliance/gst/returns', 'GST returns', 'Compliance', 'gst', 'gst.file', 'erp', 430),
    ('erp.compliance.gst.reconciliation', '/compliance/gst/reconciliation', 'GSTR-2B', 'Compliance', 'gst', 'tax.read', 'erp', 440),
    ('erp.compliance.tds', '/compliance/tds', 'TDS overview', 'Compliance', 'tds', 'tax.read', 'erp', 450),
    ('erp.compliance.tds.returns', '/compliance/tds/returns', 'TDS returns', 'Compliance', 'tds', 'tds.file', 'erp', 460),
    ('erp.compliance.dashboard', '/compliance/dashboard', 'Compliance dashboard', 'Compliance', 'compliance', 'tax.read', 'erp', 470),
    ('erp.compliance.obligations', '/compliance/obligations', 'Obligations', 'Compliance', 'compliance', 'tax.read', 'erp', 480),
    ('erp.compliance.calendar', '/compliance/calendar', 'Calendar', 'Compliance', 'compliance', 'tax.read', 'erp', 490),
    ('erp.compliance.notices', '/compliance/notices', 'Notices', 'Compliance', 'compliance', 'tax.read', 'erp', 500),
    ('erp.compliance.risk', '/compliance/risk', 'Tax risk', 'Compliance', 'compliance', 'tax.read', 'erp', 510),
    ('erp.compliance.events', '/compliance/events', 'Events', 'Compliance', 'compliance', 'audit.read', 'erp', 520),
    ('erp.treasury.dashboard', '/treasury/dashboard', 'Treasury dashboard', 'Treasury', 'treasury', 'treasury.read', 'erp', 530),
    ('erp.treasury.cash_position', '/treasury/cash-position', 'Cash position', 'Treasury', 'treasury', 'treasury.read', 'erp', 540),
    ('erp.treasury.liquidity', '/treasury/liquidity', 'Liquidity', 'Treasury', 'treasury', 'treasury.read', 'erp', 550),
    ('erp.treasury.forecast', '/treasury/forecast', 'Cash forecast', 'Treasury', 'treasury', 'treasury.read', 'erp', 560),
    ('erp.treasury.transfers', '/treasury/transfers', 'Inter-account transfers', 'Treasury', 'treasury', 'treasury.transfer', 'erp', 570),
    ('erp.treasury.alerts', '/treasury/alerts', 'Liquidity alerts', 'Treasury', 'treasury', 'treasury.read', 'erp', 580),
    ('erp.treasury.banking.dashboard', '/treasury/banking/dashboard', 'Banking dashboard', 'Treasury', 'banking', 'bank.read', 'erp', 590),
    ('erp.treasury.banking.accounts', '/treasury/banking/accounts', 'Bank accounts', 'Treasury', 'banking', 'bank.read', 'erp', 600),
    ('erp.treasury.banking.transactions', '/treasury/banking/transactions', 'Transactions', 'Treasury', 'banking', 'bank.read', 'erp', 610),
    ('erp.treasury.banking.payments', '/treasury/banking/payments', 'Bank payments', 'Treasury', 'banking', 'payment.approve', 'erp', 620),
    ('erp.treasury.banking.receipts', '/treasury/banking/receipts', 'Bank receipts', 'Treasury', 'banking', 'bank.read', 'erp', 630),
    ('erp.treasury.banking.beneficiaries', '/treasury/banking/beneficiaries', 'Beneficiaries', 'Treasury', 'banking', 'banking.manage', 'erp', 640),
    ('erp.treasury.reconciliation.dashboard', '/treasury/reconciliation/dashboard', 'Reconciliation dashboard', 'Treasury', 'reconciliation', 'bank.reconcile', 'erp', 650),
    ('erp.treasury.reconciliation', '/treasury/reconciliation', 'Workbench', 'Treasury', 'reconciliation', 'bank.reconcile', 'erp', 660),
    ('erp.treasury.reconciliation.history', '/treasury/reconciliation/history', 'Match history', 'Treasury', 'reconciliation', 'bank.reconcile', 'erp', 670),
    ('erp.treasury.reconciliation.exceptions', '/treasury/reconciliation/exceptions', 'Exceptions', 'Treasury', 'reconciliation', 'bank.reconcile', 'erp', 680),
    ('erp.treasury.reconciliation.adjustments', '/treasury/reconciliation/adjustments', 'Adjustments', 'Treasury', 'reconciliation', 'bank.reconcile', 'erp', 690),
    ('erp.intelligence.invoice_ai', '/intelligence/invoice-ai', 'Invoice AI', 'Intelligence', 'invoice_ai', 'invoice.ai.review', 'erp', 700),
    ('erp.intelligence.workflow', '/intelligence/workflow', 'Workflow intelligence', 'Intelligence', 'workflow_intelligence', 'workflow.read', 'erp', 710),
    ('erp.intelligence.agents', '/intelligence/agents', 'Agents', 'Intelligence', 'agents', 'agent.run', 'erp', 720),
    ('erp.intelligence.memory', '/intelligence/memory', 'Memory', 'Intelligence', 'memory', 'memory.read', 'erp', 730),
    ('erp.intelligence.graph', '/intelligence/graph', 'Graph', 'Intelligence', 'graph_engine', 'graph.read', 'erp', 740),
    ('erp.intelligence.forecasting', '/intelligence/forecasting', 'Forecasting', 'Intelligence', 'forecasting', 'forecast.read', 'erp', 750),
    ('erp.reports', '/reports', 'Report hub', 'Reporting', 'reporting', 'report.read', 'erp', 760),
    ('erp.reports.trial_balance', '/reports/trial-balance', 'Trial balance', 'Reporting', 'reporting', 'report.read', 'erp', 770),
    ('erp.reports.pnl', '/reports/pnl', 'Profit & loss', 'Reporting', 'reporting', 'report.read', 'erp', 780),
    ('erp.reports.balance_sheet', '/reports/balance-sheet', 'Balance sheet', 'Reporting', 'reporting', 'report.read', 'erp', 790),
    ('erp.reports.ap_aging', '/reports/ap-aging', 'AP aging report', 'Reporting', 'reporting', 'report.read', 'erp', 800),
    ('erp.reports.ar_aging', '/reports/ar-aging', 'AR aging report', 'Reporting', 'reporting', 'report.read', 'erp', 810),
    ('erp.reports.gst', '/reports/gst', 'GST summary', 'Reporting', 'reporting', 'report.read', 'erp', 820),
    ('erp.reports.tds', '/reports/tds', 'TDS summary', 'Reporting', 'reporting', 'report.read', 'erp', 830),
    ('erp.reports.consolidation', '/reports/consolidation', 'Consolidation', 'Reporting', 'consolidation', 'report.read', 'erp', 840),
    ('erp.reports.consolidation.entities', '/reports/consolidation/entities', 'Entity hierarchy', 'Reporting', 'consolidation', 'report.read', 'erp', 850),
    ('erp.reports.consolidation.intercompany', '/reports/consolidation/intercompany', 'Intercompany', 'Reporting', 'consolidation', 'report.read', 'erp', 860),
    ('erp.reports.consolidation.runs', '/reports/consolidation/runs', 'Consolidation runs', 'Reporting', 'consolidation', 'report.read', 'erp', 870),
    ('erp.governance.audit', '/governance/audit', 'Audit Explorer', 'Governance', 'audit_explorer', 'audit.read', 'erp', 880),
    ('erp.governance.violations', '/governance/violations', 'Violations', 'Governance', 'audit_explorer', 'audit.read', 'erp', 890),
    ('admin.platform.users', '/admin/platform/users', 'Users', 'Administration', NULL, 'user.manage', 'admin', 900),
    ('admin.platform.roles', '/admin/platform/roles', 'Roles', 'Administration', NULL, 'user.manage', 'admin', 910),
    ('admin.platform.roles.permissions', '/admin/platform/roles/permissions', 'Permissions', 'Administration', NULL, 'user.manage', 'admin', 920),
    ('admin.platform.org', '/admin/platform/org', 'Organization', 'Administration', NULL, 'organization.manage', 'admin', 930),
    ('admin.platform.integrations', '/admin/platform/integrations', 'Integrations & API', 'Administration', NULL, 'integration.manage', 'admin', 940),
    ('admin.platform.security.sessions', '/admin/platform/security/sessions', 'Sessions', 'Administration', NULL, 'session.read', 'admin', 950),
    ('admin.platform.security.mfa', '/admin/platform/security/mfa', 'MFA', 'Administration', NULL, NULL, 'admin', 960),
    ('admin.platform.billing', '/admin/platform/billing', 'Billing', 'Administration', NULL, 'billing.admin', 'admin', 970),
    ('admin.platform.activity', '/admin/platform/activity', 'Activity', 'Administration', NULL, 'audit.read', 'admin', 980),
    ('admin.platform.recycle_bin', '/admin/platform/recycle-bin', 'Recycle bin', 'Administration', NULL, 'audit.read', 'admin', 990),
    ('erp.support', '/support', 'Support', 'Administration', NULL, 'organization.manage', 'erp', 1000),
    ('admin.governance.policies', '/admin/governance/policies', 'Policy Engine', 'Administration', NULL, 'policy.manage', 'admin', 1010),
    ('admin.governance.approval_matrix', '/admin/governance/approval-matrix', 'Approval Matrix', 'Administration', NULL, 'policy.manage', 'admin', 1020),
    ('admin.governance.forensics', '/admin/governance/forensics', 'Forensics', 'Administration', NULL, 'audit.read', 'admin', 1030),
    ('admin.notifications.templates', '/admin/notifications/templates', 'Notification templates', 'Administration', NULL, 'notification.manage', 'admin', 1040),
    ('platform.root', '/platform', 'Platform overview', 'Platform', NULL, 'platform.admin', 'platform', 1050),
    ('platform.orgs', '/platform/orgs', 'Organizations', 'Platform', NULL, 'platform.admin', 'platform', 1060),
    ('platform.users', '/platform/users', 'Users', 'Platform', NULL, 'platform.admin', 'platform', 1070),
    ('platform.usage', '/platform/usage', 'Usage', 'Platform', NULL, 'platform.admin', 'platform', 1080),
    ('platform.commercial', '/platform/commercial', 'Commercial', 'Platform', NULL, 'platform.admin', 'platform', 1090),
    ('platform.features', '/platform/features', 'Features', 'Platform', NULL, 'platform.admin', 'platform', 1100),
    ('platform.support', '/platform/support', 'Platform support', 'Platform', NULL, 'platform.admin', 'platform', 1110),
    ('platform.activity', '/platform/activity', 'Platform activity', 'Platform', NULL, 'platform.admin', 'platform', 1120),
    ('platform.recycle_bin', '/platform/recycle-bin', 'Platform recycle bin', 'Platform', NULL, 'platform.admin', 'platform', 1130),
    ('platform.ops.queues', '/platform/ops/queues', 'Queues', 'Platform', NULL, 'platform.admin', 'platform', 1140),
    ('platform.ops.jobs', '/platform/ops/jobs', 'Jobs', 'Platform', NULL, 'platform.admin', 'platform', 1150),
    ('platform.ops.events', '/platform/ops/events', 'Events', 'Platform', NULL, 'platform.admin', 'platform', 1160),
    ('platform.ops.workers', '/platform/ops/workers', 'Workers', 'Platform', NULL, 'platform.admin', 'platform', 1170),
    ('platform.ops.webhook_deliveries', '/platform/ops/webhook-deliveries', 'Webhook deliveries', 'Platform', NULL, 'platform.admin', 'platform', 1180),
    ('platform.observability', '/platform/observability', 'Observability', 'Platform', NULL, 'platform.admin', 'platform', 1190),
    ('platform.ai', '/platform/ai', 'AI ops', 'Platform', NULL, 'platform.admin', 'platform', 1200)
ON CONFLICT (screen_key) DO UPDATE SET
    route_path = EXCLUDED.route_path,
    label = EXCLUDED.label,
    nav_category = EXCLUDED.nav_category,
    feature_code = EXCLUDED.feature_code,
    permission_key = EXCLUDED.permission_key,
    console = EXCLUDED.console,
    sort_order = EXCLUDED.sort_order,
    status = 'active',
    updated_at = NOW();

-- ---------------------------------------------------------------------------
-- Org / user controls
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform.org_controls (
    org_id UUID PRIMARY KEY REFERENCES core.organizations(id) ON DELETE CASCADE,
    lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'active',
    login_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    ai_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    erp_modules_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    api_access_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    support_priority VARCHAR(16) NOT NULL DEFAULT 'standard',
    notes TEXT NULL,
    updated_by UUID NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS platform.user_controls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    denied_feature_codes TEXT[] NOT NULL DEFAULT '{}',
    denied_screen_keys TEXT[] NOT NULL DEFAULT '{}',
    force_read_only BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'platform_owner',
    expires_at TIMESTAMPTZ NULL,
    created_by UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, user_id)
);

CREATE INDEX IF NOT EXISTS platform_user_controls_user_idx ON platform.user_controls (user_id);

-- ---------------------------------------------------------------------------
-- Support tickets
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS support.tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    created_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    assigned_to_user_id UUID NULL,
    subject VARCHAR(500) NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'other',
    priority VARCHAR(16) NOT NULL DEFAULT 'normal',
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    related_feature_code VARCHAR(64) NULL,
    related_org_control_note TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS support_tickets_org_status_idx
    ON support.tickets (org_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS support.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES support.tickets(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    author_user_id UUID NOT NULL,
    author_side VARCHAR(16) NOT NULL,
    body TEXT NOT NULL,
    attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS support_messages_ticket_idx
    ON support.messages (ticket_id, created_at ASC);

CREATE TABLE IF NOT EXISTS support.ticket_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES support.tickets(id) ON DELETE CASCADE,
    org_id UUID NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    actor_user_id UUID NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Activity events
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform.activity_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    actor_user_id UUID NULL,
    actor_type VARCHAR(32) NOT NULL DEFAULT 'user',
    action VARCHAR(32) NOT NULL,
    entity_type VARCHAR(128) NULL,
    entity_id TEXT NULL,
    screen_key VARCHAR(128) NULL,
    feature_code VARCHAR(64) NULL,
    summary TEXT NULL,
    before_snapshot_id UUID NULL,
    after_hash VARCHAR(128) NULL,
    request_id VARCHAR(128) NULL,
    ip_address VARCHAR(64) NULL,
    user_agent TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS platform_activity_org_created_idx
    ON platform.activity_events (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS platform_activity_entity_idx
    ON platform.activity_events (org_id, entity_type, entity_id);

-- ---------------------------------------------------------------------------
-- Recycle bin + entity registry
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform.entity_type_registry (
    entity_type VARCHAR(128) PRIMARY KEY,
    schema_name VARCHAR(64) NOT NULL,
    table_name VARCHAR(128) NOT NULL,
    soft_delete_column VARCHAR(64) NULL,
    snapshot_query_key VARCHAR(128) NULL,
    retention_days INT NOT NULL DEFAULT 30,
    requires_platform_restore BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO platform.entity_type_registry
    (entity_type, schema_name, table_name, soft_delete_column, retention_days, requires_platform_restore)
VALUES
    ('core.user', 'core', 'users', NULL, 90, TRUE),
    ('erp.vendor', 'erp', 'vendors', NULL, 30, FALSE),
    ('erp.customer', 'erp', 'customers', NULL, 30, FALSE),
    ('platform.document', 'platform', 'documents', NULL, 30, FALSE)
ON CONFLICT (entity_type) DO NOTHING;

CREATE TABLE IF NOT EXISTS platform.recycle_bin (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    entity_type VARCHAR(128) NOT NULL REFERENCES platform.entity_type_registry(entity_type),
    entity_id TEXT NOT NULL,
    snapshot JSONB NOT NULL,
    schema_version INT NOT NULL DEFAULT 1,
    deleted_by UUID NULL,
    deleted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delete_reason TEXT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'user',
    restore_status VARCHAR(32) NOT NULL DEFAULT 'available',
    restored_at TIMESTAMPTZ NULL,
    restored_by UUID NULL,
    purge_after TIMESTAMPTZ NULL,
    activity_event_id UUID NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS platform_recycle_bin_org_status_idx
    ON platform.recycle_bin (org_id, restore_status, deleted_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS platform_recycle_bin_available_uq
    ON platform.recycle_bin (org_id, entity_type, entity_id)
    WHERE restore_status = 'available';

-- Seed org_controls for existing orgs
INSERT INTO platform.org_controls (org_id)
SELECT id FROM core.organizations
ON CONFLICT (org_id) DO NOTHING;

-- Ensure billing plans rows exist with credits from known defaults (idempotent inserts)
INSERT INTO billing.plans (plan_key, name, tier, monthly_price_inr, included_ai_credits, status)
VALUES
    ('finance_starter', 'Finance Starter', 1, 0, 0, 'active'),
    ('finance_growth', 'Finance Growth', 2, 0, 500, 'active'),
    ('finance_os_pro', 'Finance OS Pro', 3, 0, 2000, 'active'),
    ('enterprise', 'Enterprise', 4, 0, 0, 'active')
ON CONFLICT (plan_key) DO NOTHING;
