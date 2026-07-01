#!/usr/bin/env python3
"""Generate docs/FRONTEND_MODULES_REFERENCE.md from schema extract + module config."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRACT = ROOT / "docs" / ".frontend_api_extract.json"
OUTPUT = ROOT / "docs" / "FRONTEND_MODULES_REFERENCE.md"
GEN_SCRIPT = Path(__file__).resolve().parent / "gen_frontend_module_docs.py"

SCHEMAS: dict = {}
ROUTES: dict = {}


def load_extract() -> None:
    global SCHEMAS, ROUTES
    if not EXTRACT.exists():
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, str(GEN_SCRIPT)],
            capture_output=True,
            text=True,
            check=True,
        )
        EXTRACT.write_text(result.stdout, encoding="utf-8")
    data = json.loads(EXTRACT.read_text(encoding="utf-8-sig"))
    SCHEMAS = data.get("schemas", {})
    ROUTES = data.get("routes_by_module", {})


def field_table(model: str, schema_key: str | None = None) -> str:
    models = None
    if schema_key and schema_key in SCHEMAS:
        models = SCHEMAS[schema_key]
    else:
        for sk, m in SCHEMAS.items():
            if model in m:
                models = m
                break
    if not models or model not in models:
        return f"_See OpenAPI `/docs` for `{model}`._\n"
    rows = ["| Field | Type | Required | Default |", "|-------|------|----------|---------|"]
    for f in models[model]:
        req = "yes" if f["required"] else "no"
        default = f.get("default")
        if default is None:
            default = "—"
        elif isinstance(default, str) and "Field(" in default:
            default = "—"
        rows.append(f"| `{f['name']}` | `{f['type']}` | {req} | {default} |")
    return "\n".join(rows) + "\n"


def api_block(
    method: str,
    path: str,
    *,
    auth: str = "required",
    permission: str = "—",
    request_model: str | None = None,
    response_model: str | None = None,
    query: str = "—",
    ui_trigger: str = "—",
    schema_key: str | None = None,
) -> str:
    lines = [
        f"#### `{method}` `/api/v1{path}`",
        "",
        f"- **Auth:** {auth}",
        f"- **Permission:** `{permission}`",
        f"- **Query params:** {query}",
        f"- **UI trigger:** {ui_trigger}",
        "",
    ]
    if request_model:
        lines += [f"**Request — `{request_model}`**", "", field_table(request_model, schema_key), ""]
    if response_model:
        lines += [f"**Response — `{response_model}`**", "", field_table(response_model, schema_key), ""]
    lines += ["**Errors:** `400` validation · `401` auth · `403` permission · `404` not found · `409` idempotent replay", ""]
    return "\n".join(lines)


def screen_block(name: str, route: str, purpose: str, apis: list[str], components: list[str]) -> str:
    lines = [
        f"#### Screen: {name}",
        "",
        f"- **Route:** `{route}`",
        f"- **Purpose:** {purpose}",
        "- **API calls:**",
    ]
    for a in apis:
        lines.append(f"  - {a}")
    lines += ["- **Component tree:**"]
    for c in components:
        lines.append(f"  - {c}")
    lines.append("")
    return "\n".join(lines)


def module_section(
    mid: str,
    title: str,
    purpose: str,
    prefix: str,
    erp_doc: str,
    schema_paths: list[str],
    deps: list[str],
    permissions: list[str],
    screens: list[dict],
    apis: list[dict],
) -> str:
    anchor = mid.lower().replace(" ", "-")
    lines = [
        f"## {mid} — {title}",
        "",
        f"**Backend spec:** [{erp_doc}](./ERP_MODULES/{erp_doc})",
        "",
        "### Overview",
        "",
        purpose,
        "",
        f"- **API prefix:** `/api/v1{prefix}`",
        "- **Schema paths:**",
    ]
    for sp in schema_paths:
        lines.append(f"  - `backend/apps/api/app/modules/{sp}`")
    lines += ["- **Dependencies:** " + (", ".join(deps) if deps else "None"), "- **Key permissions:** " + ", ".join(f"`{p}`" for p in permissions), "", "### Screens and Components", ""]
    for s in screens:
        lines.append(screen_block(s["name"], s["route"], s["purpose"], s["apis"], s["components"]))
    lines += ["### API Reference", ""]
    for a in apis:
        lines.append(api_block(**a))
    lines.append("---\n")
    return "\n".join(lines)


MODULES = [
    {
        "mid": "M01",
        "title": "Identity & Access Management (IAM)",
        "purpose": "Authentication, users, roles, permissions, organizations, MFA, and API keys.",
        "prefix": "",
        "erp_doc": "M01_iam.md",
        "schema_paths": ["core/iam/schemas/auth_schema.py", "core/iam/schemas/user_schema.py", "core/iam/schemas/role_schema.py"],
        "deps": [],
        "permissions": ["user.manage", "role.manage", "org.manage"],
        "screens": [
            {"name": "Login", "route": "/login", "purpose": "Email/password and MFA login.",
             "apis": ["POST /auth/login", "POST /auth/refresh", "GET /me"],
             "components": ["LoginForm", "MFAInput", "PermissionGate"]},
            {"name": "User List", "route": "/admin/platform/users", "purpose": "Manage tenant users.",
             "apis": ["GET /users", "POST /users", "PATCH /users/{user_id}"],
             "components": ["PageHeader", "DataTable", "UserFormModal", "RoleAssignDialog"]},
            {"name": "Role Editor", "route": "/admin/platform/roles", "purpose": "CRUD roles and permissions.",
             "apis": ["GET /roles", "POST /roles", "POST /roles/{role_id}/permissions"],
             "components": ["RoleForm", "PermissionCheckboxTree"]},
            {"name": "Org Settings", "route": "/admin/platform/org", "purpose": "Companies, branches, business units.",
             "apis": ["GET /organizations/current", "POST /organizations/companies", "POST /organizations/branches"],
             "components": ["OrgTree", "CompanyForm", "BranchForm"]},
        ],
        "apis": [
            {"method": "POST", "path": "/auth/login", "auth": "public", "request_model": "LoginRequest", "response_model": "LoginResponse", "schema_key": "core/iam/schemas/auth_schema.py", "ui_trigger": "Login screen submit"},
            {"method": "POST", "path": "/auth/refresh", "auth": "public", "request_model": "RefreshRequest", "response_model": "RefreshResponse", "schema_key": "core/iam/schemas/auth_schema.py", "ui_trigger": "Token refresh timer"},
            {"method": "POST", "path": "/auth/logout", "auth": "optional", "request_model": "LogoutRequest", "schema_key": "core/iam/schemas/auth_schema.py", "ui_trigger": "Sign out"},
            {"method": "GET", "path": "/me", "response_model": "MeResponse", "ui_trigger": "App boot / session hydrate"},
            {"method": "GET", "path": "/users", "permission": "user.manage", "ui_trigger": "User list page load"},
            {"method": "POST", "path": "/users", "permission": "user.manage", "ui_trigger": "Create user modal"},
            {"method": "GET", "path": "/roles", "permission": "role.manage", "ui_trigger": "Role editor load"},
        ],
    },
    {
        "mid": "M02",
        "title": "Workflow Engine",
        "purpose": "Unified workflow definitions, instances, tasks, approvals, escalations, and SLA.",
        "prefix": "",
        "erp_doc": "M02_workflow.md",
        "schema_paths": ["workflows/schemas/workflow_schema.py", "workflows/schemas/approval_schema.py"],
        "deps": ["M01 IAM", "M04 Governance"],
        "permissions": ["workflow.approve", "workflow.manage"],
        "screens": [
            {"name": "Approval Inbox", "route": "/workflows/approvals", "purpose": "Pending approvals queue.",
             "apis": ["GET /approvals", "POST /approvals/{approval_id}/decide"],
             "components": ["ApprovalCard", "ApprovalActions", "PolicyDecisionPanel", "AmountThresholdBadge"]},
            {"name": "Task Inbox", "route": "/workflows/tasks", "purpose": "Assigned workflow tasks.",
             "apis": ["GET /tasks", "POST /tasks/{task_id}/complete", "POST /tasks/{task_id}/assign"],
             "components": ["TaskList", "TaskAssignee", "WorkflowTimeline"]},
            {"name": "Workflow Detail", "route": "/workflows/[id]", "purpose": "Instance state and audit.",
             "apis": ["GET /workflows/{workflow_id}", "POST /workflows/{workflow_id}/transition", "GET /workflows/instances/{workflow_id}/audit"],
             "components": ["WorkflowTimeline", "StatusBadge", "AuditTrailLink"]},
        ],
        "apis": [
            {"method": "POST", "path": "/workflows/start", "request_model": "WorkflowStartRequest", "schema_key": "workflows/schemas/workflow_schema.py", "ui_trigger": "Submit for approval actions"},
            {"method": "GET", "path": "/approvals", "query": "`status`, `limit`", "ui_trigger": "Approval inbox load"},
            {"method": "POST", "path": "/approvals/{approval_id}/decide", "request_model": "ApprovalDecideRequest", "schema_key": "workflows/schemas/approval_schema.py", "ui_trigger": "Approve/reject button"},
            {"method": "GET", "path": "/tasks", "ui_trigger": "Task inbox load"},
            {"method": "GET", "path": "/workflows/events/stream/sse", "ui_trigger": "Realtime workflow updates"},
        ],
    },
    {
        "mid": "M03",
        "title": "Event Bus + Async Execution",
        "purpose": "Platform event catalog, queues, DLQ, and replay (admin/ops UI only).",
        "prefix": "",
        "erp_doc": "M03_event_bus.md",
        "schema_paths": ["platform/events/schemas/event_schema.py"],
        "deps": [],
        "permissions": ["ops.admin"],
        "screens": [
            {"name": "Event Catalog", "route": "/admin/ops/events", "purpose": "Browse registered event types.",
             "apis": ["GET /events/catalog", "GET /events/registry/{event_type}"],
             "components": ["DataTable", "EventTypeDetail"]},
            {"name": "Queue Topology", "route": "/admin/ops/queues", "purpose": "Monitor queue lag and DLQ.",
             "apis": ["GET /queue/topology", "POST /queues/{queue_name}/dlq/requeue"],
             "components": ["QueueStatusGrid", "DLQRequeueButton"]},
        ],
        "apis": [
            {"method": "GET", "path": "/events/catalog", "permission": "ops.admin", "ui_trigger": "Event catalog page"},
            {"method": "GET", "path": "/queue/topology", "permission": "ops.admin", "ui_trigger": "Queue ops page"},
            {"method": "POST", "path": "/events/publish", "permission": "ops.admin", "ui_trigger": "Manual event publish (ops)"},
        ],
    },
    {
        "mid": "M04",
        "title": "Audit, Compliance & Governance Core",
        "purpose": "Immutable audit logs, evidence links, policy evaluation, violations, and forensics.",
        "prefix": "",
        "erp_doc": "M04_governance.md",
        "schema_paths": [],
        "deps": ["M01 IAM"],
        "permissions": ["audit.read", "policy.manage"],
        "screens": [
            {"name": "Audit Log Explorer", "route": "/admin/governance/audit-logs", "purpose": "Search and export audit logs.",
             "apis": ["GET /audit/logs", "GET /audit/timeline/{entity_type}/{entity_id}", "GET /audit/export"],
             "components": ["FilterBar", "AuditLogTable", "TimelineView", "ExportButton"]},
            {"name": "Policy Simulator", "route": "/admin/governance/policies", "purpose": "Test policy rules before deploy.",
             "apis": ["GET /policies", "POST /policies/simulate", "POST /policies/evaluate"],
             "components": ["PolicyForm", "SimulationResultPanel", "ApprovalMatrixEditor"]},
        ],
        "apis": [
            {"method": "GET", "path": "/audit/logs", "query": "`entity_type`, `entity_id`, `from`, `to`", "ui_trigger": "Audit explorer load"},
            {"method": "POST", "path": "/policies/evaluate", "ui_trigger": "Pre-action policy check"},
            {"method": "GET", "path": "/governance/violations", "ui_trigger": "Violations dashboard"},
            {"method": "GET", "path": "/governance/forensics/timeline", "ui_trigger": "Forensics view"},
        ],
    },
    {
        "mid": "M05",
        "title": "Notification & Communication Engine",
        "purpose": "In-app notifications, preferences, templates, and Action Center SSE feed.",
        "prefix": "",
        "erp_doc": "M05_notifications.md",
        "schema_paths": ["platform/notifications/schemas/notification_schema.py", "platform/notifications/schemas/preference_schema.py"],
        "deps": ["M03 Event Bus"],
        "permissions": ["notification.read"],
        "screens": [
            {"name": "Notification Center", "route": "/notifications", "purpose": "History, ack, snooze.",
             "apis": ["GET /notifications", "POST /notifications/{id}/acknowledge", "GET /notifications/unread-count"],
             "components": ["NotificationList", "UnreadBadge", "SnoozeMenu"]},
            {"name": "Preferences", "route": "/notifications/preferences", "purpose": "Channel and quiet hours.",
             "apis": ["GET /preferences", "POST /preferences"],
             "components": ["PreferenceForm", "QuietHoursPicker"]},
        ],
        "apis": [
            {"method": "GET", "path": "/notifications", "query": "`unread_only`, `limit`", "ui_trigger": "Notification center / badge"},
            {"method": "GET", "path": "/realtime/action-center/sse", "ui_trigger": "ActionCenter SSE subscription"},
            {"method": "POST", "path": "/notifications/{id}/acknowledge", "ui_trigger": "Mark read"},
        ],
    },
    {
        "mid": "M06",
        "title": "Document Management System (DMS)",
        "purpose": "Upload, OCR, extraction, evidence links, semantic search, and previews.",
        "prefix": "",
        "erp_doc": "M06_documents.md",
        "schema_paths": ["platform/documents/schemas/document_schema.py", "platform/documents/schemas/extraction_schema.py"],
        "deps": ["M01 IAM"],
        "permissions": ["document.upload", "document.read"],
        "screens": [
            {"name": "Document Library", "route": "/documents", "purpose": "Browse and filter documents.",
             "apis": ["GET /documents", "GET /documents/{document_id}/previews"],
             "components": ["DataTable", "DocumentPreview", "StatusBadge"]},
            {"name": "Upload Wizard", "route": "/documents/upload", "purpose": "Cloudinary signed upload flow.",
             "apis": ["POST /uploads/cloudinary/sign", "POST /uploads/cloudinary/finalize", "POST /ocr/request"],
             "components": ["CloudinaryUploader", "UploadProgress", "ConfidenceBadge"]},
            {"name": "OCR Review", "route": "/documents/[id]/review", "purpose": "Correct extractions.",
             "apis": ["GET /documents/{id}", "POST /documents/extractions/correct", "POST /documents/classify"],
             "components": ["SplitPane", "ExtractionReviewForm", "ConfidenceField"]},
        ],
        "apis": [
            {"method": "POST", "path": "/uploads/cloudinary/sign", "ui_trigger": "Upload wizard step 1"},
            {"method": "POST", "path": "/uploads/cloudinary/finalize", "ui_trigger": "Upload wizard step 3"},
            {"method": "GET", "path": "/documents", "query": "`doc_type`, `status`, `limit`", "ui_trigger": "Library load"},
            {"method": "GET", "path": "/documents/search/hybrid", "query": "`q`", "ui_trigger": "Document search"},
            {"method": "POST", "path": "/documents/extractions/correct", "ui_trigger": "Review form submit"},
        ],
    },
    {
        "mid": "M07",
        "title": "Integration Platform",
        "purpose": "Connectors, webhooks, sync jobs, ingestion, and integration API keys.",
        "prefix": "/integrations",
        "erp_doc": "M07_integrations.md",
        "schema_paths": ["platform/integrations/schemas/connector_schema.py", "platform/integrations/schemas/webhook_schema.py"],
        "deps": ["M01 IAM", "M03 Event Bus"],
        "permissions": ["integration.manage"],
        "screens": [
            {"name": "Connectors", "route": "/admin/platform/integrations/connectors", "purpose": "Configure ERP/bank connectors.",
             "apis": ["GET /integrations/connectors", "POST /integrations/connectors"],
             "components": ["ConnectorCard", "ConnectorConfigForm", "SyncStatusBadge"]},
            {"name": "Webhooks", "route": "/admin/platform/integrations/webhooks", "purpose": "Outbound webhook subscriptions.",
             "apis": ["GET /integrations/webhooks/subscriptions", "POST /integrations/webhooks/subscriptions"],
             "components": ["WebhookTable", "DeliveryLogDrawer"]},
        ],
        "apis": [
            {"method": "GET", "path": "/integrations/connectors", "ui_trigger": "Connector list"},
            {"method": "POST", "path": "/integrations/connectors", "ui_trigger": "Add connector"},
            {"method": "GET", "path": "/integrations/sync/jobs", "ui_trigger": "Sync job monitor"},
        ],
    },
    {
        "mid": "M08",
        "title": "Chart of Accounts (COA)",
        "purpose": "Account groups, chart hierarchy, cost centers, and GST/financial mappings.",
        "prefix": "/erp",
        "erp_doc": "M08_coa.md",
        "schema_paths": ["erp/coa/schemas/account_schema.py"],
        "deps": ["M01 IAM"],
        "permissions": ["coa.manage"],
        "screens": [
            {"name": "COA Tree", "route": "/accounting/coa", "purpose": "Hierarchical account structure.",
             "apis": ["GET /erp/coa/tree", "GET /erp/account-groups"],
             "components": ["TreeView", "AccountGroupForm", "AccountPicker"]},
            {"name": "Account List", "route": "/accounting/coa/accounts", "purpose": "CRUD postable accounts.",
             "apis": ["GET /erp/accounts", "POST /erp/accounts", "PUT /erp/accounts/{account_id}"],
             "components": ["DataTable", "AccountForm", "StatusBadge"]},
        ],
        "apis": [
            {"method": "POST", "path": "/erp/account-groups", "ui_trigger": "Create account group"},
            {"method": "POST", "path": "/erp/accounts", "ui_trigger": "Create account"},
            {"method": "GET", "path": "/erp/coa/tree", "ui_trigger": "COA tree page"},
            {"method": "GET", "path": "/erp/accounts/search", "query": "`q`", "ui_trigger": "AccountPicker search"},
        ],
    },
    {
        "mid": "M09",
        "title": "General Ledger (GL)",
        "purpose": "Posting, balances, trial balance, ledger entries, and batch reversal.",
        "prefix": "/erp",
        "erp_doc": "M09_gl.md",
        "schema_paths": ["erp/gl/schemas/posting_schema.py"],
        "deps": ["M08 COA", "M10 Journals"],
        "permissions": ["journal.post", "gl.read"],
        "screens": [
            {"name": "Trial Balance", "route": "/accounting/gl/trial-balance", "purpose": "Period trial balance view.",
             "apis": ["GET /erp/trial-balance", "GET /erp/reports/trial-balance"],
             "components": ["ReportTable", "PeriodSelector", "LedgerGrid"]},
            {"name": "Ledger Entries", "route": "/accounting/gl/ledger", "purpose": "Detailed ledger drill-down.",
             "apis": ["GET /erp/ledger/entries"],
             "components": ["LedgerGrid", "FilterBar", "AccountPicker"]},
        ],
        "apis": [
            {"method": "POST", "path": "/erp/gl/post", "ui_trigger": "Manual GL post (admin)"},
            {"method": "GET", "path": "/erp/trial-balance", "query": "`fiscal_period_id`", "ui_trigger": "Trial balance page"},
            {"method": "GET", "path": "/erp/ledger/entries", "query": "`account_id`, `from`, `to`", "ui_trigger": "Ledger page"},
            {"method": "POST", "path": "/erp/gl/batches/{batch_id}/reverse", "ui_trigger": "Reverse batch action"},
        ],
    },
    {
        "mid": "M10",
        "title": "Journal Engine",
        "purpose": "Manual/recurring/accrual journals, approval queue, posting, and reversals.",
        "prefix": "/erp",
        "erp_doc": "M10_journals.md",
        "schema_paths": ["erp/journals/schemas/journal_schema.py", "erp/journals/schemas/recurring_schema.py"],
        "deps": ["M08 COA", "M02 Workflow", "M09 GL"],
        "permissions": ["journal.create", "journal.approve", "journal.post"],
        "screens": [
            {"name": "Journal List", "route": "/accounting/journals", "purpose": "Browse journals by status.",
             "apis": ["GET /erp/journals"],
             "components": ["DataTable", "FilterBar", "StatusBadge"]},
            {"name": "Journal Editor", "route": "/accounting/journals/[id]", "purpose": "Create/edit journal lines.",
             "apis": ["GET /erp/journals/{journal_id}", "POST /erp/journals", "PUT /erp/journals/{journal_id}"],
             "components": ["LineItemsEditor", "AccountPicker", "FiscalPeriodPicker", "ApprovalActions"]},
            {"name": "Approval Queue", "route": "/accounting/journals/approval-queue", "purpose": "Pending journal approvals.",
             "apis": ["GET /erp/journals/approval-queue", "POST /erp/journals/{id}/approve"],
             "components": ["ApprovalCard", "LedgerGrid", "PolicyDecisionPanel"]},
        ],
        "apis": [
            {"method": "POST", "path": "/erp/journals", "request_model": "JournalCreateRequest", "schema_key": "erp/journals/schemas/journal_schema.py", "ui_trigger": "Create journal"},
            {"method": "GET", "path": "/erp/journals/{journal_id}", "ui_trigger": "Journal detail load"},
            {"method": "POST", "path": "/erp/journals/{id}/submit", "ui_trigger": "Submit for approval"},
            {"method": "POST", "path": "/erp/journals/{id}/approve", "ui_trigger": "Approve journal"},
            {"method": "POST", "path": "/erp/postings/{journal_id}/post", "ui_trigger": "Post to GL"},
            {"method": "POST", "path": "/erp/journals/ai/from-document", "ui_trigger": "AI journal from document"},
        ],
    },
    {
        "mid": "M11-V",
        "title": "Voucher Engine",
        "purpose": "Sales/purchase/payment/receipt/contra/journal vouchers → journal generation.",
        "prefix": "/erp",
        "erp_doc": "M11_voucher.md",
        "schema_paths": ["erp/vouchers/schemas/voucher_schema.py"],
        "deps": ["M10 Journals", "M08 COA"],
        "permissions": ["voucher.create", "voucher.approve"],
        "screens": [
            {"name": "Voucher List", "route": "/accounting/vouchers", "purpose": "All voucher types.",
             "apis": ["GET /erp/vouchers"],
             "components": ["DataTable", "FilterBar", "VoucherTypeBadge"]},
            {"name": "Voucher Wizard", "route": "/accounting/vouchers/new/[type]", "purpose": "Type-specific voucher entry.",
             "apis": ["POST /erp/vouchers/purchase", "POST /erp/vouchers/{id}/submit", "POST /erp/vouchers/{id}/post"],
             "components": ["VoucherForm", "LineItemsEditor", "PartyPicker", "ApprovalActions"]},
        ],
        "apis": [
            {"method": "POST", "path": "/erp/vouchers", "ui_trigger": "Create generic voucher"},
            {"method": "POST", "path": "/erp/vouchers/purchase", "ui_trigger": "Purchase voucher wizard"},
            {"method": "POST", "path": "/erp/vouchers/{id}/approve", "ui_trigger": "Approve voucher"},
            {"method": "POST", "path": "/erp/vouchers/{id}/generate-journal", "ui_trigger": "Generate journal"},
            {"method": "POST", "path": "/erp/vouchers/{id}/post", "ui_trigger": "Post voucher"},
        ],
    },
    {
        "mid": "M11-AP",
        "title": "Accounts Payable (AP)",
        "purpose": "Vendor master, AP invoices, payments, aging, and vendor statement reconciliation.",
        "prefix": "/ap",
        "erp_doc": "M11_ap.md",
        "schema_paths": ["erp/accounts_payable/schemas/ap_schema.py"],
        "deps": ["M06 Documents", "M10 Journals", "M02 Workflow", "M25 Invoice AI"],
        "permissions": ["invoice.create", "invoice.approve", "payment.schedule"],
        "screens": [
            {"name": "Vendor List", "route": "/operations/ap/vendors", "purpose": "Vendor master data.",
             "apis": ["GET /ap/vendors", "POST /ap/vendors"],
             "components": ["DataTable", "VendorForm", "VendorPicker"]},
            {"name": "AP Invoice Detail", "route": "/operations/ap/invoices/[id]", "purpose": "Review, approve, cancel invoice.",
             "apis": ["GET /ap/invoices/{id}", "POST /ap/invoices/{id}/submit", "POST /ap/invoices/{id}/approve"],
             "components": ["DetailHeader", "LineItemsEditor", "ExtractionReviewForm", "WorkflowTimeline", "ApprovalActions"]},
            {"name": "Payment Schedule", "route": "/operations/ap/payments", "purpose": "Schedule and track payments.",
             "apis": ["GET /ap/payments", "POST /ap/payments/schedule", "GET /ap/payments/recommendations"],
             "components": ["PaymentScheduleTable", "AIRecommendationCard", "BankAccountPicker"]},
            {"name": "AP Aging", "route": "/operations/ap/aging", "purpose": "Aging buckets and cashflow forecast.",
             "apis": ["GET /ap/aging", "GET /ap/aging/cashflow-forecast"],
             "components": ["AgingBucketChart", "TrendChart", "VendorBalanceTable"]},
        ],
        "apis": [
            {"method": "POST", "path": "/ap/vendors", "request_model": "VendorCreateRequest", "response_model": "VendorResponse", "schema_key": "erp/accounts_payable/schemas/ap_schema.py", "ui_trigger": "Create vendor"},
            {"method": "POST", "path": "/ap/invoices", "request_model": "InvoiceCreateRequest", "schema_key": "erp/accounts_payable/schemas/ap_schema.py", "ui_trigger": "Create invoice"},
            {"method": "POST", "path": "/ap/invoices/{id}/approve", "request_model": "InvoiceApproveRequest", "schema_key": "erp/accounts_payable/schemas/ap_schema.py", "ui_trigger": "Approve invoice"},
            {"method": "POST", "path": "/ap/invoices/ai/from-document", "request_model": "AiInvoiceFromDocumentRequest", "schema_key": "erp/accounts_payable/schemas/ap_schema.py", "ui_trigger": "AI invoice from document"},
            {"method": "POST", "path": "/ap/payments/schedule", "request_model": "PaymentScheduleRequest", "schema_key": "erp/accounts_payable/schemas/ap_schema.py", "ui_trigger": "Schedule payment"},
            {"method": "GET", "path": "/ap/aging", "ui_trigger": "Aging dashboard"},
        ],
    },
    {
        "mid": "M12-AR",
        "title": "Accounts Receivable (AR)",
        "purpose": "Customers, AR invoices, collections, credit check, and aging.",
        "prefix": "/ar",
        "erp_doc": "M12_ar.md",
        "schema_paths": ["erp/accounts_receivable/schemas/ar_schema.py"],
        "deps": ["M10 Journals", "M02 Workflow"],
        "permissions": ["ar.invoice.create", "ar.collection.manage"],
        "screens": [
            {"name": "Customer List", "route": "/operations/ar/customers", "purpose": "Customer master.",
             "apis": ["GET /ar/customers", "POST /ar/customers"],
             "components": ["DataTable", "CustomerForm", "CustomerPicker"]},
            {"name": "AR Invoice Issue", "route": "/operations/ar/invoices/[id]", "purpose": "Issue, cancel, write-off.",
             "apis": ["GET /ar/invoices/{id}", "POST /ar/invoices/{id}/issue"],
             "components": ["DetailHeader", "LineItemsEditor", "TaxLineEditor"]},
            {"name": "Collections", "route": "/operations/ar/collections", "purpose": "Receipts and forecast.",
             "apis": ["GET /ar/collections/receipts", "POST /ar/collections/assistant"],
             "components": ["ReceiptTable", "AIRecommendationCard", "CopilotAskBar"]},
        ],
        "apis": [
            {"method": "POST", "path": "/ar/customers", "ui_trigger": "Create customer"},
            {"method": "POST", "path": "/ar/invoices", "ui_trigger": "Create AR invoice"},
            {"method": "POST", "path": "/ar/invoices/{id}/issue", "ui_trigger": "Issue invoice"},
            {"method": "POST", "path": "/ar/credit/check", "ui_trigger": "Credit check before issue"},
            {"method": "GET", "path": "/ar/aging", "ui_trigger": "AR aging dashboard"},
        ],
    },
    {
        "mid": "M12-F",
        "title": "Fiscal Period Management",
        "purpose": "Fiscal years, periods, period close checklist, and year-end.",
        "prefix": "/erp/ledger",
        "erp_doc": "M12_fiscal.md",
        "schema_paths": ["erp/fiscal/schemas/fiscal_schema.py"],
        "deps": ["M09 GL", "M10 Journals"],
        "permissions": ["period.close"],
        "screens": [
            {"name": "Fiscal Periods", "route": "/accounting/fiscal/periods", "purpose": "List and manage periods.",
             "apis": ["GET /erp/ledger/periods", "POST /erp/ledger/periods/{period_id}/close"],
             "components": ["DataTable", "FiscalPeriodPicker", "StatusBadge"]},
            {"name": "Period Close", "route": "/accounting/fiscal/close/[periodId]", "purpose": "Close checklist workflow.",
             "apis": ["GET /erp/ledger/periods/{period_id}/close/checklist", "POST /erp/ledger/periods/{period_id}/close/submit"],
             "components": ["CloseChecklist", "WorkflowTimeline", "ApprovalActions"]},
        ],
        "apis": [
            {"method": "GET", "path": "/erp/ledger/fiscal-years", "ui_trigger": "Fiscal year list"},
            {"method": "GET", "path": "/erp/ledger/periods", "ui_trigger": "Period list"},
            {"method": "POST", "path": "/erp/ledger/periods/{period_id}/close/init", "ui_trigger": "Initiate close"},
            {"method": "POST", "path": "/erp/ledger/periods/{period_id}/close/submit", "ui_trigger": "Submit close"},
        ],
    },
    {
        "mid": "M14",
        "title": "GST, Taxation & Compliance Engine",
        "purpose": "GST calculations, ITC, returns, e-invoice, e-way bill, TDS/TCS, and challans.",
        "prefix": "/gst, /tds, /tax/compliance",
        "erp_doc": "M14_tax.md",
        "schema_paths": ["erp/tax/schemas/tax_schema.py"],
        "deps": ["M11 AP", "M12 AR", "M10 Journals"],
        "permissions": ["gst.file", "tds.file"],
        "screens": [
            {"name": "GST Dashboard", "route": "/compliance/gst", "purpose": "ITC summary, transactions, returns.",
             "apis": ["GET /gst/itc/summary", "GET /gst/returns", "POST /gst/returns/generate"],
             "components": ["KPICard", "ReportTable", "FilingStatusBadge"]},
            {"name": "TDS Dashboard", "route": "/compliance/tds", "purpose": "TDS transactions, challans, returns.",
             "apis": ["GET /tds/liability", "POST /tds/challan", "POST /tds/returns/generate"],
             "components": ["ReportTable", "ChallanForm", "SectionPicker"]},
        ],
        "apis": [
            {"method": "POST", "path": "/gst/calculate", "ui_trigger": "GST calculation on invoice line"},
            {"method": "GET", "path": "/gst/itc/summary", "ui_trigger": "GST dashboard"},
            {"method": "POST", "path": "/gst/returns/{id}/submit", "ui_trigger": "Submit GST return"},
            {"method": "POST", "path": "/gst/e-invoice/{invoice_id}/generate", "ui_trigger": "Generate e-invoice"},
            {"method": "POST", "path": "/tds/calculate", "ui_trigger": "TDS calculation"},
            {"method": "GET", "path": "/tax/compliance/calendar/upcoming", "ui_trigger": "Tax compliance calendar widget"},
        ],
    },
    {
        "mid": "M15",
        "title": "Procurement Engine",
        "purpose": "Purchase requisitions, POs, GRNs, and 3-way matching.",
        "prefix": "/erp/procurement",
        "erp_doc": "M15_procurement.md",
        "schema_paths": ["erp/procurement/schemas/procurement_schema.py"],
        "deps": ["M11 AP", "M18 Inventory"],
        "permissions": ["procurement.approve"],
        "screens": [
            {"name": "Purchase Requisitions", "route": "/operations/procurement/pr", "purpose": "PR lifecycle.",
             "apis": ["GET /erp/procurement/pr", "POST /erp/procurement/pr/{pr_id}/submit"],
             "components": ["DataTable", "PRForm", "ApprovalActions"]},
            {"name": "3-Way Match", "route": "/operations/procurement/matches", "purpose": "PO-GRN-Invoice match review.",
             "apis": ["GET /erp/procurement/matches", "POST /erp/procurement/match/{match_id}/override"],
             "components": ["MatchReviewPanel", "LineItemsEditor", "OverrideReasonForm"]},
        ],
        "apis": [
            {"method": "POST", "path": "/erp/procurement/pr", "ui_trigger": "Create PR"},
            {"method": "POST", "path": "/erp/procurement/po", "ui_trigger": "Create PO"},
            {"method": "POST", "path": "/erp/procurement/grn", "ui_trigger": "Create GRN"},
            {"method": "GET", "path": "/erp/procurement/matches", "ui_trigger": "Match review list"},
        ],
    },
    {
        "mid": "M16",
        "title": "Expense Management",
        "purpose": "Employee expense claims, receipts, policies, and reimbursement.",
        "prefix": "/erp/expenses",
        "erp_doc": "M16_expense.md",
        "schema_paths": ["erp/expenses/schemas/expense_schema.py"],
        "deps": ["M06 Documents", "M02 Workflow"],
        "permissions": ["expense.submit", "expense.approve"],
        "screens": [
            {"name": "Expense Claims", "route": "/operations/expenses/claims", "purpose": "Claim list and submission.",
             "apis": ["GET /erp/expenses/claims", "POST /erp/expenses/claims/{id}/submit"],
             "components": ["DataTable", "ClaimForm", "ReceiptUpload"]},
        ],
        "apis": [
            {"method": "POST", "path": "/erp/expenses/claims", "ui_trigger": "Create claim"},
            {"method": "POST", "path": "/erp/expenses/receipts/from-document", "ui_trigger": "Receipt from document OCR"},
            {"method": "POST", "path": "/erp/expenses/claims/{claim_id}/reimburse", "ui_trigger": "Reimburse approved claim"},
        ],
    },
    {
        "mid": "M17",
        "title": "Fixed Assets",
        "purpose": "Asset register, capitalization, depreciation, transfer, impairment, disposal.",
        "prefix": "/erp/assets",
        "erp_doc": "M17_assets.md",
        "schema_paths": ["erp/assets/schemas/asset_schema.py"],
        "deps": ["M11 AP", "M10 Journals"],
        "permissions": ["asset.manage"],
        "screens": [
            {"name": "Asset Register", "route": "/operations/assets/register", "purpose": "Asset list and detail.",
             "apis": ["GET /erp/assets/register", "GET /erp/assets/{asset_id}"],
             "components": ["DataTable", "AssetDetail", "DepreciationSchedule"]},
        ],
        "apis": [
            {"method": "POST", "path": "/erp/assets", "ui_trigger": "Create asset"},
            {"method": "POST", "path": "/erp/assets/{asset_id}/capitalize", "ui_trigger": "Capitalize asset"},
            {"method": "POST", "path": "/erp/assets/depreciate", "ui_trigger": "Run depreciation"},
        ],
    },
    {
        "mid": "M18",
        "title": "Inventory & Stock Accounting",
        "purpose": "Items, warehouses, receipts, issues, transfers, adjustments, valuation.",
        "prefix": "/erp/inventory",
        "erp_doc": "M18_inventory.md",
        "schema_paths": ["erp/inventory/schemas/inventory_schema.py"],
        "deps": ["M15 Procurement"],
        "permissions": ["inventory.manage"],
        "screens": [
            {"name": "Inventory Items", "route": "/operations/inventory/items", "purpose": "Item master and balances.",
             "apis": ["GET /erp/inventory/items", "GET /erp/inventory/balances"],
             "components": ["DataTable", "ItemForm", "StockLevelBadge"]},
        ],
        "apis": [
            {"method": "POST", "path": "/erp/inventory/items", "ui_trigger": "Create item"},
            {"method": "POST", "path": "/erp/inventory/receipts/from-grn", "ui_trigger": "Receipt from GRN"},
            {"method": "GET", "path": "/erp/inventory/valuation", "ui_trigger": "Valuation report"},
        ],
    },
    {
        "mid": "M21",
        "title": "Compliance Calendar",
        "purpose": "Regulatory obligations, deadlines, readiness, and risk dashboard.",
        "prefix": "/erp/compliance",
        "erp_doc": "M21_compliance.md",
        "schema_paths": ["erp/compliance/schemas/compliance_schema.py"],
        "deps": ["M14 Tax"],
        "permissions": ["compliance.read"],
        "screens": [
            {"name": "Compliance Calendar", "route": "/compliance/calendar", "purpose": "Upcoming filings and obligations.",
             "apis": ["GET /erp/compliance/calendar/upcoming", "GET /erp/compliance/obligations"],
             "components": ["CalendarView", "ObligationCard", "ReadinessScore"]},
        ],
        "apis": [
            {"method": "GET", "path": "/erp/compliance/calendar", "ui_trigger": "Calendar page"},
            {"method": "GET", "path": "/erp/compliance/dashboard", "ui_trigger": "Readiness dashboard"},
            {"method": "POST", "path": "/erp/compliance/copilot", "ui_trigger": "Compliance copilot"},
        ],
    },
    {
        "mid": "M22",
        "title": "Banking Engine",
        "purpose": "Bank accounts, statement import, payments, beneficiaries, receipts.",
        "prefix": "/erp/banking",
        "erp_doc": "M22_banking.md",
        "schema_paths": ["erp/banking/schemas/banking_schema.py"],
        "deps": ["M11 AP", "M12 AR"],
        "permissions": ["payment.execute", "banking.manage"],
        "screens": [
            {"name": "Bank Accounts", "route": "/treasury/banking/accounts", "purpose": "Manage bank accounts.",
             "apis": ["GET /erp/banking/accounts", "POST /erp/banking/accounts"],
             "components": ["DataTable", "BankAccountForm", "BankAccountPicker"]},
            {"name": "Bank Payments", "route": "/treasury/banking/payments", "purpose": "Payment execution after approval.",
             "apis": ["GET /erp/banking/payments", "POST /erp/banking/payments/{id}/execute"],
             "components": ["PaymentTable", "ApprovalActions", "ExecutionStatusBadge"]},
        ],
        "apis": [
            {"method": "POST", "path": "/erp/banking/accounts", "ui_trigger": "Add bank account"},
            {"method": "POST", "path": "/erp/banking/statements/import", "ui_trigger": "Import bank statement"},
            {"method": "POST", "path": "/erp/banking/payments/{id}/execute", "ui_trigger": "Execute payment"},
            {"method": "POST", "path": "/erp/banking/copilot", "ui_trigger": "Banking copilot"},
        ],
    },
    {
        "mid": "M23",
        "title": "Reconciliation Engine",
        "purpose": "Bank, vendor, and customer reconciliation with AI match suggestions.",
        "prefix": "/erp/reconciliation",
        "erp_doc": "M23_reconciliation.md",
        "schema_paths": ["erp/reconciliation/schemas/reconciliation_schema.py"],
        "deps": ["M22 Banking", "M11 AP", "M12 AR"],
        "permissions": ["reconciliation.approve"],
        "screens": [
            {"name": "Bank Reconciliation", "route": "/treasury/reconciliation", "purpose": "Match bank vs book lines.",
             "apis": ["GET /erp/reconciliation/bank", "POST /erp/reconciliation/suggest", "POST /erp/reconciliation/match"],
             "components": ["SplitPane", "ReconciliationGrid", "MatchSuggestionPanel", "AIRecommendationCard"]},
            {"name": "Exception Queue", "route": "/treasury/reconciliation/exceptions", "purpose": "Unresolved exceptions.",
             "apis": ["GET /erp/reconciliation/exceptions", "POST /erp/reconciliation/exceptions/{id}/assign"],
             "components": ["ExceptionTable", "AssignmentDialog"]},
        ],
        "apis": [
            {"method": "GET", "path": "/erp/reconciliation/bank", "ui_trigger": "Bank recon workspace load"},
            {"method": "POST", "path": "/erp/reconciliation/suggest", "ui_trigger": "Request AI match suggestions"},
            {"method": "POST", "path": "/erp/reconciliation/{reconciliation_id}/approve", "ui_trigger": "Approve match"},
            {"method": "POST", "path": "/erp/reconciliation/copilot", "ui_trigger": "Recon copilot"},
        ],
    },
    {
        "mid": "M24",
        "title": "Treasury Management",
        "purpose": "Cash position, liquidity, forecasts, transfers, and alerts.",
        "prefix": "/erp/treasury",
        "erp_doc": "M24_treasury.md",
        "schema_paths": ["erp/treasury/schemas/treasury_schema.py"],
        "deps": ["M22 Banking", "M30 Forecasting"],
        "permissions": ["treasury.transfer", "treasury.read"],
        "screens": [
            {"name": "Cash Position", "route": "/treasury/cash-position", "purpose": "Live cash position dashboard.",
             "apis": ["GET /erp/treasury/cash-position", "GET /erp/treasury/cash-position/history"],
             "components": ["KPICard", "TrendChart", "CashPositionBreakdown"]},
            {"name": "Treasury Transfers", "route": "/treasury/transfers", "purpose": "Inter-account transfers.",
             "apis": ["GET /erp/treasury/transfers", "POST /erp/treasury/transfers/{id}/approve"],
             "components": ["TransferForm", "ApprovalActions", "BankAccountPicker"]},
        ],
        "apis": [
            {"method": "GET", "path": "/erp/treasury/cash-position", "ui_trigger": "Cash position dashboard"},
            {"method": "GET", "path": "/erp/treasury/liquidity", "ui_trigger": "Liquidity analysis"},
            {"method": "POST", "path": "/erp/treasury/transfers", "ui_trigger": "Create transfer"},
            {"method": "GET", "path": "/erp/treasury/alerts", "ui_trigger": "Treasury alerts panel"},
        ],
    },
    {
        "mid": "M25",
        "title": "AI Invoice Intelligence",
        "purpose": "Extract, predict, duplicate detection, anomalies, and copilot for invoices.",
        "prefix": "/finance-os/invoice-ai",
        "erp_doc": "M25_invoice_ai.md",
        "schema_paths": ["finance_os/invoice_ai/schemas/invoice_ai_schema.py"],
        "deps": ["M06 Documents"],
        "permissions": ["invoice.ai.review"],
        "screens": [
            {"name": "Invoice AI Review", "route": "/intelligence/invoice-ai", "purpose": "Review AI extractions and predictions.",
             "apis": ["POST /finance-os/invoice-ai/extract", "POST /finance-os/invoice-ai/predict", "GET /finance-os/invoice-ai/anomalies"],
             "components": ["ExtractionReviewForm", "ConfidenceBadge", "DuplicateConfirmDialog", "CopilotPanel"]},
        ],
        "apis": [
            {"method": "POST", "path": "/finance-os/invoice-ai/extract", "request_model": "ExtractRequest", "schema_key": "finance_os/invoice_ai/schemas/invoice_ai_schema.py", "ui_trigger": "Extract from document"},
            {"method": "POST", "path": "/finance-os/invoice-ai/predict", "request_model": "PredictRequest", "schema_key": "finance_os/invoice_ai/schemas/invoice_ai_schema.py", "ui_trigger": "Predict accounts/codes"},
            {"method": "GET", "path": "/finance-os/invoice-ai/duplicates", "ui_trigger": "Duplicate detection panel"},
            {"method": "POST", "path": "/finance-os/invoice-ai/copilot", "ui_trigger": "Invoice copilot ask"},
        ],
    },
    {
        "mid": "M26",
        "title": "Workflow Intelligence",
        "purpose": "Bottleneck analytics, SLA risks, predictions, and recommendations.",
        "prefix": "/finance-os/workflow-intelligence",
        "erp_doc": "M26_workflow_intelligence.md",
        "schema_paths": ["finance_os/workflow_intelligence/schemas/workflow_intelligence_schema.py"],
        "deps": ["M02 Workflow"],
        "permissions": ["workflow.read"],
        "screens": [
            {"name": "Workflow Analytics", "route": "/intelligence/workflow", "purpose": "Bottlenecks and SLA risks.",
             "apis": ["GET /finance-os/workflow-intelligence/bottlenecks", "GET /finance-os/workflow-intelligence/sla-risks"],
             "components": ["TrendChart", "BottleneckHeatmap", "RecommendationList"]},
        ],
        "apis": [
            {"method": "GET", "path": "/finance-os/workflow-intelligence/bottlenecks", "ui_trigger": "Analytics dashboard"},
            {"method": "GET", "path": "/finance-os/workflow-intelligence/recommendations", "ui_trigger": "Recommendations panel"},
            {"method": "POST", "path": "/finance-os/workflow-intelligence/recommendations/{id}/accept", "ui_trigger": "Accept recommendation"},
        ],
    },
    {
        "mid": "M27",
        "title": "Enterprise Financial Memory",
        "purpose": "Entity-scoped memory, insights, search, and admin decay.",
        "prefix": "/finance-os/memory",
        "erp_doc": "M27_memory.md",
        "schema_paths": ["finance_os/memory/schemas/memory_schema.py"],
        "deps": [],
        "permissions": ["memory.read"],
        "screens": [
            {"name": "Entity Memory", "route": "/intelligence/memory/[type]/[id]", "purpose": "Memory for a finance entity.",
             "apis": ["GET /finance-os/memory/entity/{type}/{id}", "GET /finance-os/memory/insights"],
             "components": ["MemoryTimeline", "InsightFeed", "CopilotPanel"]},
        ],
        "apis": [
            {"method": "GET", "path": "/finance-os/memory/entity/{type}/{id}", "ui_trigger": "Entity memory panel"},
            {"method": "POST", "path": "/finance-os/memory/write", "request_model": "MemoryWriteRequest", "schema_key": "finance_os/memory/schemas/memory_schema.py", "ui_trigger": "Save memory note"},
            {"method": "GET", "path": "/finance-os/memory/search", "query": "`q`", "ui_trigger": "Memory search"},
        ],
    },
    {
        "mid": "M28",
        "title": "Operational Graph Engine",
        "purpose": "Entity relationships, lineage, root-cause, and visualization.",
        "prefix": "/finance-os/graph",
        "erp_doc": "M28_graph.md",
        "schema_paths": ["finance_os/graph/schemas/graph_schema.py"],
        "deps": ["M27 Memory"],
        "permissions": ["graph.read"],
        "screens": [
            {"name": "Graph Explorer", "route": "/intelligence/graph/[entityId]", "purpose": "Visual entity graph.",
             "apis": ["GET /finance-os/graph/entity/{entity_id}", "GET /finance-os/graph/visualization/{entity_id}"],
             "components": ["LineageGraph", "EntityNodeCard", "CopilotPanel"]},
        ],
        "apis": [
            {"method": "GET", "path": "/finance-os/graph/entity/{entity_id}", "ui_trigger": "Graph explorer load"},
            {"method": "GET", "path": "/finance-os/graph/lineage/{entity_id}", "ui_trigger": "Lineage panel"},
            {"method": "GET", "path": "/finance-os/graph/root-cause/{entity_id}", "ui_trigger": "Root cause analysis"},
            {"method": "POST", "path": "/finance-os/graph/copilot", "ui_trigger": "Graph copilot"},
        ],
    },
    {
        "mid": "M29",
        "title": "AI Agent Orchestration",
        "purpose": "Agent catalog, runs, approvals, and domain shortcuts (AP, recon, GST, close).",
        "prefix": "/finance-os/agents",
        "erp_doc": "M29_agents.md",
        "schema_paths": ["finance_os/agents/schemas/agents_schema.py", "finance_os/agents/schemas/api_schema.py"],
        "deps": ["M02 Workflow", "M04 Governance"],
        "permissions": ["agent.run", "agent.approve"],
        "screens": [
            {"name": "Agent Runs", "route": "/intelligence/agents", "purpose": "Monitor and approve agent runs.",
             "apis": ["GET /finance-os/agents/executions", "POST /finance-os/agents/runs/{run_id}/approve"],
             "components": ["AgentRunTable", "HumanApprovalGate", "CitationList", "ConfidenceBadge"]},
        ],
        "apis": [
            {"method": "GET", "path": "/finance-os/agents/catalog", "ui_trigger": "Agent catalog"},
            {"method": "POST", "path": "/finance-os/agents/run", "ui_trigger": "Start agent run"},
            {"method": "POST", "path": "/finance-os/agents/runs/{run_id}/approve", "ui_trigger": "Approve agent action"},
            {"method": "POST", "path": "/finance-os/agents/ap/run", "ui_trigger": "AP agent shortcut"},
        ],
    },
    {
        "mid": "M30",
        "title": "Forecasting Engine",
        "purpose": "Cash, collections, expenses, tax, working capital forecasts and scenarios.",
        "prefix": "/finance-os/forecasting",
        "erp_doc": "M30_forecasting.md",
        "schema_paths": ["finance_os/forecasting/schemas/forecasting_schema.py"],
        "deps": ["M31 Reporting", "M24 Treasury"],
        "permissions": ["forecast.read"],
        "screens": [
            {"name": "Forecasting Dashboard", "route": "/intelligence/forecasting", "purpose": "Multi-series forecasts.",
             "apis": ["GET /finance-os/forecasting/cash", "GET /finance-os/forecasting/dashboard", "GET /finance-os/forecasting/scenarios"],
             "components": ["TrendChart", "ScenarioSelector", "KPICard"]},
        ],
        "apis": [
            {"method": "GET", "path": "/finance-os/forecasting/cash", "ui_trigger": "Cash forecast chart"},
            {"method": "GET", "path": "/finance-os/forecasting/collections", "ui_trigger": "Collections forecast"},
            {"method": "GET", "path": "/finance-os/forecasting/dashboard", "ui_trigger": "Forecast dashboard"},
        ],
    },
    {
        "mid": "M31",
        "title": "Reporting Engine",
        "purpose": "Canonical ERP reports from pre-aggregated snapshots; async export.",
        "prefix": "/erp/reports",
        "erp_doc": "M31_reporting.md",
        "schema_paths": ["erp/reporting/schemas/reporting_schema.py"],
        "deps": ["M09 GL", "M11 AP", "M12 AR", "M14 Tax"],
        "permissions": ["report.read"],
        "screens": [
            {"name": "Report Hub", "route": "/reports", "purpose": "Navigate all report types.",
             "apis": ["GET /erp/reports/trial-balance", "GET /erp/reports/pnl", "GET /erp/reports/balance-sheet"],
             "components": ["ReportCardGrid", "PeriodSelector"]},
            {"name": "Export Status", "route": "/reports/exports/[runId]", "purpose": "Poll async export jobs.",
             "apis": ["POST /erp/reports/export", "GET /erp/reports/export/{run_id}"],
             "components": ["AsyncExportPoller", "DownloadButton"]},
        ],
        "apis": [
            {"method": "GET", "path": "/erp/reports/trial-balance", "ui_trigger": "Trial balance report"},
            {"method": "GET", "path": "/erp/reports/pnl", "ui_trigger": "P&L report"},
            {"method": "GET", "path": "/erp/reports/ap-aging", "ui_trigger": "AP aging report"},
            {"method": "POST", "path": "/erp/reports/export", "ui_trigger": "Start export job"},
        ],
    },
    {
        "mid": "M32",
        "title": "Analytics & Business Intelligence",
        "purpose": "Executive KPIs, trends, insights, benchmarks, and copilot.",
        "prefix": "/finance-os/analytics",
        "erp_doc": "M32_analytics.md",
        "schema_paths": ["finance_os/analytics/schemas/analytics_schema.py"],
        "deps": ["M31 Reporting", "M30 Forecasting"],
        "permissions": ["analytics.read"],
        "screens": [
            {"name": "Executive Dashboard", "route": "/dashboard", "purpose": "Primary KPI landing page.",
             "apis": ["GET /finance-os/analytics/dashboard", "GET /finance-os/analytics/kpis"],
             "components": ["DashboardGrid", "KPICard", "TrendChart", "InsightFeed", "CopilotAskBar"]},
        ],
        "apis": [
            {"method": "GET", "path": "/finance-os/analytics/dashboard", "ui_trigger": "Main dashboard load"},
            {"method": "GET", "path": "/finance-os/analytics/kpis", "ui_trigger": "KPI drill-down"},
            {"method": "GET", "path": "/finance-os/analytics/trends", "ui_trigger": "Trend charts"},
            {"method": "POST", "path": "/finance-os/analytics/copilot/ask", "ui_trigger": "Analytics copilot"},
        ],
    },
    {
        "mid": "M33",
        "title": "Audit Explorer",
        "purpose": "Unified audit search, explore, timeline, evidence, and AI decision trails.",
        "prefix": "/finance-os/audit",
        "erp_doc": "M33_audit_explorer.md",
        "schema_paths": [],
        "deps": ["M04 Governance", "M02 Workflow", "M28 Graph"],
        "permissions": ["audit.read"],
        "screens": [
            {"name": "Audit Search", "route": "/governance/audit", "purpose": "Cross-system audit search.",
             "apis": ["GET /finance-os/audit/search", "GET /finance-os/audit/explore/{object_type}/{object_id}"],
             "components": ["SearchBar", "AuditResultList", "TimelineView"]},
            {"name": "Object Explore", "route": "/governance/audit/[type]/[id]", "purpose": "Full explainable story for object.",
             "apis": ["GET /finance-os/audit/timeline/{object_type}/{object_id}", "GET /finance-os/audit/evidence/{object_type}/{object_id}"],
             "components": ["ExplorerView", "EvidenceChain", "ApprovalChainView", "AIDecisionPanel"]},
        ],
        "apis": [
            {"method": "GET", "path": "/finance-os/audit/search", "query": "`q`, `object_type`", "ui_trigger": "Audit search"},
            {"method": "GET", "path": "/finance-os/audit/explore/{object_type}/{object_id}", "ui_trigger": "Explore view"},
            {"method": "GET", "path": "/finance-os/audit/timeline/{object_type}/{object_id}", "ui_trigger": "Timeline panel"},
            {"method": "POST", "path": "/finance-os/audit/copilot/ask", "ui_trigger": "Audit copilot"},
        ],
    },
    {
        "mid": "M34",
        "title": "Policy Engine",
        "purpose": "Unified policy evaluation, approval matrix, SoD, and exceptions (via M04 governance APIs).",
        "prefix": "/governance/policies",
        "erp_doc": "M34_policy_engine.md",
        "schema_paths": [],
        "deps": ["M04 Governance", "M01 IAM"],
        "permissions": ["policy.manage"],
        "screens": [
            {"name": "Approval Matrix", "route": "/admin/governance/approval-matrix", "purpose": "INR approval tiers.",
             "apis": ["GET /policies/approval-matrix", "POST /policies/approval-matrix"],
             "components": ["ApprovalMatrixEditor", "AmountThresholdTable"]},
        ],
        "apis": [
            {"method": "POST", "path": "/policies/evaluate", "ui_trigger": "Pre-action evaluate (all modules)"},
            {"method": "GET", "path": "/policies/approval-matrix", "ui_trigger": "Approval matrix editor"},
            {"method": "GET", "path": "/policies/sod", "ui_trigger": "SoD rules viewer"},
            {"method": "GET", "path": "/policies/exceptions", "ui_trigger": "Policy exceptions list"},
        ],
    },
    {
        "mid": "M35",
        "title": "Multi-Entity Consolidation",
        "purpose": "Entity hierarchy, intercompany, consolidation runs, eliminations.",
        "prefix": "/erp/consolidation",
        "erp_doc": "M35_consolidation.md",
        "schema_paths": [],
        "deps": ["M08 COA", "M31 Reporting"],
        "permissions": ["consolidation.run"],
        "screens": [
            {"name": "Entity Hierarchy", "route": "/reports/consolidation/entities", "purpose": "Group structure.",
             "apis": ["GET /erp/consolidation/entities/hierarchy"],
             "components": ["OrgTree", "EntityCard"]},
            {"name": "Consolidation Runs", "route": "/reports/consolidation/runs", "purpose": "Run and review consolidation.",
             "apis": ["POST /erp/consolidation/consolidation/run", "GET /erp/consolidation/consolidation/runs/{run_id}"],
             "components": ["RunStatusTable", "EliminationReport", "ReportTable"]},
        ],
        "apis": [
            {"method": "GET", "path": "/erp/consolidation/entities/hierarchy", "ui_trigger": "Hierarchy view"},
            {"method": "POST", "path": "/erp/consolidation/consolidation/run", "ui_trigger": "Start consolidation"},
            {"method": "GET", "path": "/erp/consolidation/intercompany/mismatches", "ui_trigger": "IC mismatch review"},
        ],
    },
    {
        "mid": "M36",
        "title": "API + Webhook Platform",
        "purpose": "Platform-level API keys, webhooks, and event catalog for external integrators.",
        "prefix": "/platform",
        "erp_doc": "M36_api_platform.md",
        "schema_paths": ["platform/api_gateway/schemas/gateway_schema.py"],
        "deps": ["M01 IAM", "M03 Event Bus"],
        "permissions": ["api_key.manage"],
        "screens": [
            {"name": "Platform API Keys", "route": "/admin/platform/api-keys", "purpose": "External API access.",
             "apis": ["GET /platform/api-keys", "POST /platform/api-keys"],
             "components": ["ApiKeyTable", "ApiKeyCreateDialog", "ScopePicker"]},
        ],
        "apis": [
            {"method": "POST", "path": "/platform/api-keys", "ui_trigger": "Create platform API key"},
            {"method": "GET", "path": "/platform/webhooks", "ui_trigger": "Webhook list"},
            {"method": "GET", "path": "/platform/events/catalog", "ui_trigger": "Event catalog"},
        ],
    },
    {
        "mid": "M37",
        "title": "Billing & Entitlements",
        "purpose": "Subscription, plans, usage, credits, and admin billing controls.",
        "prefix": "/billing",
        "erp_doc": "M37_billing.md",
        "schema_paths": [],
        "deps": ["M01 IAM"],
        "permissions": ["billing.admin"],
        "screens": [
            {"name": "Subscription", "route": "/admin/platform/billing", "purpose": "Current plan and entitlements.",
             "apis": ["GET /billing/subscription", "GET /billing/entitlements", "GET /billing/usage"],
             "components": ["PlanCard", "UsageMeter", "CreditsBalance"]},
        ],
        "apis": [
            {"method": "GET", "path": "/billing/subscription", "ui_trigger": "Billing page load"},
            {"method": "GET", "path": "/billing/entitlements", "ui_trigger": "Feature gating check"},
            {"method": "GET", "path": "/billing/usage", "ui_trigger": "Usage dashboard"},
            {"method": "GET", "path": "/admin/billing/plans", "permission": "billing.admin", "ui_trigger": "Admin plan management"},
        ],
    },
]


APPENDIX = """
## Appendix A — Shared Type Definitions

Reused across modules. Full field lists are in backend Pydantic schemas.

| Type | Module | Key fields |
|------|--------|------------|
| `InvoiceLineInput` | M11 AP | `account_id`, `line_type`, `description`, `amount`, `tax_code`, `cost_center_id` |
| `VendorCreateRequest` | M11 AP | `vendor_name`, `gstin`, `pan`, `payment_terms_days`, `payable_account_id` |
| `JournalCreateRequest` | M10 | `journal_date`, `description`, `lines[]`, `fiscal_period_id` |
| `WorkflowStartRequest` | M02 | `workflow_key`, `entity_type`, `entity_id`, `metadata`, `amount` |
| `MemoryWriteRequest` | M27 | `memory_type`, `title`, `content`, `entity_type`, `entity_id`, `importance_score` |
| `ExtractRequest` | M25 | `document_id`, `invoice_type` |
| `PaymentScheduleRequest` | M11 AP | `vendor_id`, `payment_date`, `amount`, `bank_account_id`, `invoice_allocations[]` |

---

## Appendix B — Standard Error Envelope

```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning | UI action |
|--------|---------|-----------|
| `400` | Validation error | Show field errors |
| `401` | Auth expired/invalid | Redirect to login / refresh |
| `403` | Permission denied | Hide action; show message |
| `404` | Not found | Empty state / 404 page |
| `409` | Conflict / idempotent replay | Show "Already processed" |
| `503` | Service unavailable | Retry banner |

---

## Appendix C — Idempotency & Pagination

**Idempotency:** Include `idempotency_key` (UUID) in JSON body or `X-Idempotency-Key` header on mutating calls. Duplicate within 24h → `409`.

**Pagination:** Most list endpoints accept `limit` (default 50, max 200) and cursor/offset query params where documented in ERP module specs.

---

## Appendix D — Realtime Event Payload Shapes

### Action Center SSE (`GET /realtime/action-center/sse`)

```json
{
  "event_type": "approval.requested",
  "channel": "action_center",
  "payload": {
    "notification_id": "uuid",
    "title": "Invoice approval required",
    "entity_type": "ap_invoice",
    "entity_id": "uuid",
    "priority": "high"
  }
}
```

### Workflow SSE (`GET /workflows/events/stream/sse`)

```json
{
  "event_type": "workflow.step.completed",
  "workflow_id": "uuid",
  "step_id": "uuid",
  "status": "completed"
}
```

### Documents channel (via notification hub)

```json
{
  "event_type": "document.ocr.completed",
  "channel": "documents",
  "payload": {
    "document_id": "uuid",
    "previews": { "thumbnail_url": "...", "preview_url": "..." }
  }
}
```

---

## Appendix E — Module Dependency Graph

```mermaid
flowchart LR
    M06[M06 Documents] --> M25[M25 Invoice AI]
    M25 --> M11AP[M11 AP]
    M06 --> M11AP
    M11AP --> M10[M10 Journals]
    M10 --> M09[M09 GL]
    M08[M08 COA] --> M10
    M11AP --> M02[M02 Workflow]
    M11AP --> M22[M22 Banking]
    M22 --> M23[M23 Reconciliation]
    M09 --> M31[M31 Reporting]
    M31 --> M32[M32 Analytics]
    M04[M04 Governance] --> M33[M33 Audit Explorer]
    M02 --> M33
```

**Cross-module screen dependencies:**

| Screen | Upstream APIs |
|--------|---------------|
| AP Invoice Review | M06 previews, M25 extract/predict, M02 approvals, M34 policy evaluate |
| Payment Execute | M11 schedule, M22 execute, M02 approval, M23 post-execute recon |
| Period Close | M12 checklist, M10 open journals, M09 trial balance, M02 workflow |
| Executive Dashboard | M32 dashboard, M31 reports, M30 forecasts, M24 cash position |
"""


def main() -> None:
    load_extract()
    parts = [
        "# Frontend Modules Reference",
        "",
        "**Status:** Active — per-module API, screen, and component reference for frontend implementation",
        "**Version:** 1.0",
        "**Last updated:** 2026-06-25",
        "",
        "**Companion doc:** [FRONTEND_ARCHITECTURE.md](./FRONTEND_ARCHITECTURE.md)",
        "",
        "All paths below are relative to **`/api/v1`** unless noted.",
        "",
        "---",
        "",
        "## Table of contents",
        "",
    ]
    for i, m in enumerate(MODULES, 1):
        anchor = f"{m['mid'].lower()}--{m['title'].split('(')[0].strip().lower().replace(' ', '-').replace('&', '')[:40]}"
        parts.append(f"{i}. [{m['mid']} — {m['title']}](#{m['mid'].lower()}--{m['title'].split('(')[0].strip().lower().replace(' ', '-').replace('&', '')[:40]})")
    parts += ["", "---", ""]

    layer_headers = {
        "M01": "## Layer 1 — Platform Core\n",
        "M08": "## Layer 2 — Accounting Core\n",
        "M11-AP": "## Layer 3 — Financial Operations\n",
        "M14": "## Layer 4 — Compliance & Tax\n",
        "M22": "## Layer 5 — Treasury & Banking\n",
        "M25": "## Layer 6 — Intelligence & Automation\n",
        "M31": "## Layer 7 — Reporting & Governance\n",
    }
    for m in MODULES:
        if m["mid"] in layer_headers:
            parts.append(layer_headers[m["mid"]])
        parts.append(module_section(**m))

    parts.append(APPENDIX)
    OUTPUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(parts)} sections, {OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
