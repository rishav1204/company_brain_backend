"""Align FE nav featureCodes + wire platform control-plane screens properly."""
from __future__ import annotations

from pathlib import Path

FE = Path(r"D:\new-project-fe\apps\web\src")


def patch_nav() -> None:
    path = FE / "config" / "nav-config.ts"
    text = path.read_text(encoding="utf-8")

    # Assets / inventory feature codes
    replacements = [
        (
            'href: "/operations/assets/register", permission: "asset.read"',
            'href: "/operations/assets/register", permission: "asset.read", featureCode: "assets"',
        ),
        (
            'href: "/operations/assets/candidates", permission: "asset.read"',
            'href: "/operations/assets/candidates", permission: "asset.read", featureCode: "assets"',
        ),
        (
            'href: "/operations/inventory/summary", permission: "inventory.read"',
            'href: "/operations/inventory/summary", permission: "inventory.read", featureCode: "inventory"',
        ),
        (
            'href: "/operations/inventory/items", permission: "inventory.read"',
            'href: "/operations/inventory/items", permission: "inventory.read", featureCode: "inventory"',
        ),
        (
            'href: "/operations/inventory/movements", permission: "inventory.read"',
            'href: "/operations/inventory/movements", permission: "inventory.read", featureCode: "inventory"',
        ),
        (
            'href: "/compliance/gst", permission: "tax.read"',
            'href: "/compliance/gst", permission: "tax.read", featureCode: "gst"',
        ),
        (
            'href: "/compliance/gst/registrations", permission: "tax.read"',
            'href: "/compliance/gst/registrations", permission: "tax.read", featureCode: "gst"',
        ),
        (
            'href: "/compliance/gst/itc", permission: "tax.read"',
            'href: "/compliance/gst/itc", permission: "tax.read", featureCode: "gst"',
        ),
        (
            'href: "/compliance/gst/returns", permission: "gst.file"',
            'href: "/compliance/gst/returns", permission: "gst.file", featureCode: "gst"',
        ),
        (
            'href: "/compliance/gst/reconciliation", permission: "tax.read"',
            'href: "/compliance/gst/reconciliation", permission: "tax.read", featureCode: "gst"',
        ),
        (
            'href: "/compliance/tds", permission: "tax.read"',
            'href: "/compliance/tds", permission: "tax.read", featureCode: "tds"',
        ),
        (
            'href: "/compliance/tds/returns", permission: "tds.file"',
            'href: "/compliance/tds/returns", permission: "tds.file", featureCode: "tds"',
        ),
        (
            'href: "/compliance/dashboard", permission: "tax.read"',
            'href: "/compliance/dashboard", permission: "tax.read", featureCode: "compliance"',
        ),
        (
            'href: "/compliance/obligations", permission: "tax.read"',
            'href: "/compliance/obligations", permission: "tax.read", featureCode: "compliance"',
        ),
        (
            'href: "/compliance/calendar", permission: "tax.read"',
            'href: "/compliance/calendar", permission: "tax.read", featureCode: "compliance"',
        ),
        (
            'href: "/compliance/notices", permission: "tax.read"',
            'href: "/compliance/notices", permission: "tax.read", featureCode: "compliance"',
        ),
        (
            'href: "/compliance/risk", permission: "tax.read"',
            'href: "/compliance/risk", permission: "tax.read", featureCode: "compliance"',
        ),
        (
            'href: "/treasury/dashboard", permission: "treasury.read"',
            'href: "/treasury/dashboard", permission: "treasury.read", featureCode: "treasury"',
        ),
        (
            'href: "/treasury/cash-position", permission: "treasury.read"',
            'href: "/treasury/cash-position", permission: "treasury.read", featureCode: "treasury"',
        ),
        (
            'href: "/treasury/liquidity", permission: "treasury.read"',
            'href: "/treasury/liquidity", permission: "treasury.read", featureCode: "treasury"',
        ),
        (
            'href: "/treasury/forecast", permission: "treasury.read"',
            'href: "/treasury/forecast", permission: "treasury.read", featureCode: "treasury"',
        ),
        (
            'href: "/treasury/transfers", permission: "treasury.transfer"',
            'href: "/treasury/transfers", permission: "treasury.transfer", featureCode: "treasury"',
        ),
        (
            'href: "/treasury/alerts", permission: "treasury.read"',
            'href: "/treasury/alerts", permission: "treasury.read", featureCode: "treasury"',
        ),
        (
            'href: "/treasury/banking/dashboard", permission: "bank.read"',
            'href: "/treasury/banking/dashboard", permission: "bank.read", featureCode: "banking"',
        ),
        (
            'href: "/treasury/banking/accounts", permission: "bank.read"',
            'href: "/treasury/banking/accounts", permission: "bank.read", featureCode: "banking"',
        ),
        (
            'href: "/treasury/banking/transactions", permission: "bank.read"',
            'href: "/treasury/banking/transactions", permission: "bank.read", featureCode: "banking"',
        ),
        (
            'href: "/treasury/banking/payments", permission: "payment.approve"',
            'href: "/treasury/banking/payments", permission: "payment.approve", featureCode: "banking"',
        ),
        (
            'href: "/treasury/banking/receipts", permission: "bank.read"',
            'href: "/treasury/banking/receipts", permission: "bank.read", featureCode: "banking"',
        ),
        (
            'href: "/treasury/banking/beneficiaries", permission: "banking.manage"',
            'href: "/treasury/banking/beneficiaries", permission: "banking.manage", featureCode: "banking"',
        ),
        (
            'href: "/treasury/reconciliation/dashboard", permission: "bank.reconcile"',
            'href: "/treasury/reconciliation/dashboard", permission: "bank.reconcile", featureCode: "reconciliation"',
        ),
        (
            'href: "/treasury/reconciliation", permission: "bank.reconcile"',
            'href: "/treasury/reconciliation", permission: "bank.reconcile", featureCode: "reconciliation"',
        ),
        (
            'href: "/treasury/reconciliation/history", permission: "bank.reconcile"',
            'href: "/treasury/reconciliation/history", permission: "bank.reconcile", featureCode: "reconciliation"',
        ),
        (
            'href: "/treasury/reconciliation/exceptions", permission: "bank.reconcile"',
            'href: "/treasury/reconciliation/exceptions", permission: "bank.reconcile", featureCode: "reconciliation"',
        ),
        (
            'href: "/treasury/reconciliation/adjustments", permission: "bank.reconcile"',
            'href: "/treasury/reconciliation/adjustments", permission: "bank.reconcile", featureCode: "reconciliation"',
        ),
        (
            'href: "/reports", permission: "report.read"',
            'href: "/reports", permission: "report.read", featureCode: "reporting"',
        ),
        (
            'href: "/reports/trial-balance", permission: "report.read"',
            'href: "/reports/trial-balance", permission: "report.read", featureCode: "reporting"',
        ),
        (
            'href: "/reports/pnl", permission: "report.read"',
            'href: "/reports/pnl", permission: "report.read", featureCode: "reporting"',
        ),
        (
            'href: "/reports/balance-sheet", permission: "report.read"',
            'href: "/reports/balance-sheet", permission: "report.read", featureCode: "reporting"',
        ),
        (
            'href: "/reports/ap-aging", permission: "report.read"',
            'href: "/reports/ap-aging", permission: "report.read", featureCode: "reporting"',
        ),
        (
            'href: "/reports/ar-aging", permission: "report.read"',
            'href: "/reports/ar-aging", permission: "report.read", featureCode: "reporting"',
        ),
        (
            'href: "/reports/gst", permission: "report.read"',
            'href: "/reports/gst", permission: "report.read", featureCode: "reporting"',
        ),
        (
            'href: "/reports/tds", permission: "report.read"',
            'href: "/reports/tds", permission: "report.read", featureCode: "reporting"',
        ),
        (
            'href: "/reports/consolidation", permission: "report.read"',
            'href: "/reports/consolidation", permission: "report.read", featureCode: "consolidation"',
        ),
        (
            'href: "/reports/consolidation/entities", permission: "report.read"',
            'href: "/reports/consolidation/entities", permission: "report.read", featureCode: "consolidation"',
        ),
        (
            'href: "/reports/consolidation/intercompany", permission: "report.read"',
            'href: "/reports/consolidation/intercompany", permission: "report.read", featureCode: "consolidation"',
        ),
        (
            'href: "/reports/consolidation/runs", permission: "report.read"',
            'href: "/reports/consolidation/runs", permission: "report.read", featureCode: "consolidation"',
        ),
    ]
    for a, b in replacements:
        if b not in text:
            text = text.replace(a, b)

    # Move Activity / Recycle / Support out of Governance Audit → Administration / Support
    gov_extra = """          { label: "Activity", href: "/admin/platform/activity", permission: "audit.read" },
          { label: "Recycle bin", href: "/admin/platform/recycle-bin", permission: "audit.read" },
          { label: "Support", href: "/support", permission: "organization.manage" },
"""
    if gov_extra in text:
        text = text.replace(gov_extra, "")

    admin_platform_block_end = '{ label: "Billing", href: "/admin/platform/billing", permission: "billing.admin" },'
    insert_admin = """{ label: "Billing", href: "/admin/platform/billing", permission: "billing.admin" },
          { label: "Activity", href: "/admin/platform/activity", permission: "audit.read" },
          { label: "Recycle bin", href: "/admin/platform/recycle-bin", permission: "audit.read" },
          { label: "Support", href: "/support", permission: "organization.manage" },"""
    if 'href: "/support"' not in text.split("Administration")[-1]:
        text = text.replace(admin_platform_block_end, insert_admin, 1)
    elif insert_admin not in text:
        # ensure not still only under governance
        if 'href: "/support"' not in text:
            text = text.replace(admin_platform_block_end, insert_admin, 1)

    path.write_text(text, encoding="utf-8")
    print("nav patched")


def patch_api() -> None:
    path = FE / "lib" / "platform-operator" / "api.ts"
    text = path.read_text(encoding="utf-8")

    # Map monthly credits on plan list
    old = """  return items.map((row, i) => ({
    ...row,
    id: row.id ?? row.plan_key ?? `plan-${i}`,
    plan_key: row.plan_key ?? row.id ?? `plan-${i}`,
    name: row.name ?? row.plan_name,
  }));
}"""
    new = """  return items.map((row, i) => ({
    ...row,
    id: row.id ?? row.plan_key ?? `plan-${i}`,
    plan_key: row.plan_key ?? row.id ?? `plan-${i}`,
    name: row.name ?? row.plan_name,
    monthly_ai_credits:
      row.monthly_ai_credits ??
      (row as { included_ai_credits?: number }).included_ai_credits,
  }));
}"""
    if "included_ai_credits" not in text.split("listAdminBillingPlansForPlatform")[-1][:500]:
        if old in text:
            text = text.replace(old, new)

    # listPlatformScreens + better features unwrap already via items
    if "listPlatformScreens" not in text:
        text += """

export async function listPlatformScreens(api: ApiClient) {
  const raw = await operatorGet<unknown>(api, "/ops/platform/screens");
  return normalizeListResponse<Record<string, unknown>>(raw);
}

export async function upsertPlatformFeature(
  api: ApiClient,
  featureCode: string,
  body: Record<string, unknown>,
) {
  return operatorPut(api, `/ops/platform/features/${encodeURIComponent(featureCode)}`, {
    feature_code: featureCode,
    ...body,
  });
}
"""
    # plans list may use plans key not items
    if "listAdminBillingPlansForPlatform" in text:
        text = text.replace(
            """export async function listAdminBillingPlansForPlatform(api: ApiClient) {
  const raw = await operatorGet<unknown>(api, `${ADMIN_BILLING_PREFIX}/plans`);
  const items = normalizeListResponse<BillingPlan>(raw);""",
            """export async function listAdminBillingPlansForPlatform(api: ApiClient) {
  const raw = await operatorGet<unknown>(api, `${ADMIN_BILLING_PREFIX}/plans`);
  let items = normalizeListResponse<BillingPlan>(raw);
  if (items.length === 0 && raw && typeof raw === "object" && Array.isArray((raw as { plans?: unknown }).plans)) {
    items = (raw as { plans: BillingPlan[] }).plans;
  }""",
        )
    path.write_text(text, encoding="utf-8")
    print("api patched")


def patch_hooks() -> None:
    path = FE / "hooks" / "use-platform-operator.ts"
    text = path.read_text(encoding="utf-8")
    if "listPlatformScreens" not in text:
        text = text.replace(
            "listPlatformFeatures,",
            "listPlatformFeatures,\n  listPlatformScreens,",
        )
    if "usePlatformScreens" not in text:
        text += """

export function usePlatformScreens(enabled = true) {
  const { api, isReady } = useApi();
  return useQuery({
    queryKey: queryKeys.platformOperator.features().concat("screens"),
    enabled: isReady && enabled,
    queryFn: () => listPlatformScreens(api),
  });
}
"""
    # Fix features query key if features() exists
    path.write_text(text, encoding="utf-8")

    qk = FE / "lib" / "query-keys.ts"
    qt = qk.read_text(encoding="utf-8")
    if "features: () =>" not in qt:
        qt = qt.replace(
            'adminPlans: () => ["platform-operator", "adminPlans"] as const,',
            """adminPlans: () => ["platform-operator", "adminPlans"] as const,
    features: () => ["platform-operator", "features"] as const,
    screens: () => ["platform-operator", "screens"] as const,
    support: () => ["platform-operator", "support"] as const,
    activity: () => ["platform-operator", "activity"] as const,
    recycle: () => ["platform-operator", "recycle"] as const,""",
        )
        qk.write_text(qt, encoding="utf-8")
    print("hooks/query keys patched")


FEATURES_PAGE = r'''"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  DataTable,
  EmptyState,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@finance-os/ui";
import { PlatformGoldenRuleBanner } from "@/components/platform-operator/PlatformShell";
import {
  usePlatformFeatures,
  usePlatformOrgs,
  usePlatformScreens,
} from "@/hooks/use-platform-operator";
import { mapPlatformOperatorErrorToUserMessage } from "@/lib/platform-operator";

type Tab = "features" | "screens";

export default function PlatformFeaturesPage() {
  const [tab, setTab] = useState<Tab>("features");
  const featuresQuery = usePlatformFeatures();
  const screensQuery = usePlatformScreens();
  const orgsQuery = usePlatformOrgs();

  const loading =
    (tab === "features" && featuresQuery.isLoading) ||
    (tab === "screens" && screensQuery.isLoading);

  const featureItems = useMemo(
    () => (featuresQuery.data ?? []) as Array<Record<string, unknown>>,
    [featuresQuery.data],
  );
  const screenItems = useMemo(
    () => (screensQuery.data ?? []) as Array<Record<string, unknown>>,
    [screensQuery.data],
  );
  const orgs = orgsQuery.data?.items ?? [];

  const featureColumns: DataTableColumn<Record<string, unknown>>[] = [
    {
      id: "code",
      header: "Code",
      cell: (r) => <code className="text-xs">{String(r.feature_code ?? "")}</code>,
    },
    { id: "name", header: "Name", cell: (r) => String(r.name ?? "—") },
    { id: "category", header: "Category", cell: (r) => String(r.category ?? "—") },
    { id: "ai", header: "AI", cell: (r) => (r.is_ai ? "yes" : "no") },
    { id: "status", header: "Status", cell: (r) => String(r.status ?? "active") },
  ];

  const screenColumns: DataTableColumn<Record<string, unknown>>[] = [
    {
      id: "key",
      header: "Screen key",
      cell: (r) => <code className="text-xs">{String(r.screen_key ?? "")}</code>,
    },
    {
      id: "path",
      header: "Route",
      cell: (r) => <code className="text-xs">{String(r.route_path ?? "")}</code>,
    },
    { id: "label", header: "Label", cell: (r) => String(r.label ?? "—") },
    { id: "nav", header: "Nav category", cell: (r) => String(r.nav_category ?? "—") },
    {
      id: "feat",
      header: "Feature",
      cell: (r) => String(r.feature_code ?? "—"),
    },
    {
      id: "perm",
      header: "Permission",
      cell: (r) => String(r.permission_key ?? "—"),
    },
    { id: "console", header: "Console", cell: (r) => String(r.console ?? "erp") },
  ];

  if (loading) return <LoadingSkeleton rows={8} />;

  const err = featuresQuery.error ?? screensQuery.error ?? orgsQuery.error;
  const errMsg = err
    ? mapPlatformOperatorErrorToUserMessage((err as { status?: number }).status ?? 500, err)
    : null;

  return (
    <div>
      <PageHeader
        title="Features & screens"
        description="Catalog aligned with ERP NAV routes and platform console paths. Gates plans, nav, and org controls."
      />
      <PlatformGoldenRuleBanner />
      {errMsg ? <p className="mb-4 text-sm text-destructive">{errMsg}</p> : null}

      <div className="mb-4 flex gap-2">
        <button
          type="button"
          className={`rounded-md border px-3 py-1.5 text-sm ${tab === "features" ? "bg-primary/10 font-medium" : "hover:bg-muted"}`}
          onClick={() => setTab("features")}
        >
          Feature catalog ({featureItems.length})
        </button>
        <button
          type="button"
          className={`rounded-md border px-3 py-1.5 text-sm ${tab === "screens" ? "bg-primary/10 font-medium" : "hover:bg-muted"}`}
          onClick={() => setTab("screens")}
        >
          UI screens ({screenItems.length})
        </button>
      </div>

      {tab === "features" ? (
        featureItems.length === 0 ? (
          <EmptyState
            title="No features"
            description="Run migration 088 so platform.feature_catalog is seeded."
          />
        ) : (
          <DataTable
            data={featureItems}
            columns={featureColumns}
            getRowId={(r) => String(r.feature_code)}
          />
        )
      ) : screenItems.length === 0 ? (
        <EmptyState
          title="No screens"
          description="Run migration 088 so platform.ui_screen_registry matches product NAV."
        />
      ) : (
        <DataTable
          data={screenItems}
          columns={screenColumns}
          getRowId={(r) => String(r.screen_key)}
        />
      )}

      <div className="mt-8">
        <h2 className="mb-2 text-sm font-medium">Org controls</h2>
        <p className="mb-2 text-sm text-muted-foreground">
          Freeze login, kill AI, or disable ERP modules per tenant without redeploying.
        </p>
        <ul className="space-y-1 text-sm">
          {orgs.slice(0, 25).map((o) => (
            <li key={o.id}>
              <Link className="text-primary underline" href={`/platform/orgs/${o.id}/controls`}>
                {o.name ?? o.org_name ?? o.id}
              </Link>
            </li>
          ))}
          {orgs.length === 0 ? (
            <li className="text-muted-foreground">No organizations loaded.</li>
          ) : null}
        </ul>
      </div>
    </div>
  );
}
'''

SUPPORT_PLATFORM = r'''"use client";

import { useState } from "react";
import {
  Button,
  DataTable,
  EmptyState,
  Input,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@finance-os/ui";
import { PlatformGoldenRuleBanner } from "@/components/platform-operator/PlatformShell";
import { useApi } from "@/hooks/use-api";
import { usePlatformSupportTickets } from "@/hooks/use-platform-operator";
import {
  getPlatformSupportTicket,
  mapPlatformOperatorErrorToUserMessage,
  replyPlatformSupportTicket,
} from "@/lib/platform-operator";
import { useQueryClient } from "@tanstack/react-query";

export default function PlatformSupportPage() {
  const ticketsQuery = usePlatformSupportTickets();
  const { api } = useApi();
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [thread, setThread] = useState<{
    ticket?: Record<string, unknown>;
    messages?: Array<Record<string, unknown>>;
  } | null>(null);
  const [reply, setReply] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const items = (ticketsQuery.data ?? []) as Array<Record<string, unknown>>;

  async function openTicket(id: string) {
    setSelectedId(id);
    setErr(null);
    try {
      const t = (await getPlatformSupportTicket(api, id)) as {
        ticket?: Record<string, unknown>;
        messages?: Array<Record<string, unknown>>;
      };
      setThread(t);
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    }
  }

  async function sendReply() {
    if (!selectedId || !reply.trim()) return;
    setErr(null);
    setSending(true);
    try {
      await replyPlatformSupportTicket(api, selectedId, reply.trim());
      setReply("");
      await openTicket(selectedId);
      qc.invalidateQueries({ queryKey: ["platform-operator", "support"] });
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    } finally {
      setSending(false);
    }
  }

  if (ticketsQuery.isLoading) return <LoadingSkeleton rows={8} />;

  const listErr = ticketsQuery.error
    ? mapPlatformOperatorErrorToUserMessage(
        (ticketsQuery.error as { status?: number }).status ?? 500,
        ticketsQuery.error,
      )
    : null;

  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "subject", header: "Subject", cell: (r) => String(r.subject ?? "—") },
    {
      id: "org",
      header: "Org",
      cell: (r) => <code className="text-xs">{String(r.org_id ?? "—").slice(0, 8)}</code>,
    },
    { id: "status", header: "Status", cell: (r) => String(r.status ?? "—") },
    { id: "priority", header: "Priority", cell: (r) => String(r.priority ?? "—") },
    {
      id: "open",
      header: "",
      cell: (r) => (
        <Button variant="outline" onClick={() => openTicket(String(r.id))}>
          Open
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Support inbox"
        description="Cross-tenant tickets from ERP /support (platform.admin)"
      />
      <PlatformGoldenRuleBanner />
      {listErr || err ? <p className="mb-3 text-sm text-destructive">{listErr ?? err}</p> : null}
      {items.length === 0 ? (
        <EmptyState
          title="No tickets"
          description="Tenants open tickets at /support after migration 088 is applied."
        />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r) => String(r.id)} />
      )}
      {thread ? (
        <div className="mt-6 rounded-md border p-4">
          <h3 className="font-medium">{String(thread.ticket?.subject ?? selectedId)}</h3>
          <p className="text-xs text-muted-foreground">
            Org {String(thread.ticket?.org_id ?? "")} · {String(thread.ticket?.status ?? "")}
          </p>
          <div className="mt-3 max-h-64 space-y-2 overflow-y-auto text-sm">
            {(thread.messages ?? []).map((m) => (
              <div key={String(m.id)} className="rounded bg-muted/40 px-3 py-2">
                <div className="text-xs text-muted-foreground">
                  {String(m.author_side)} · {String(m.created_at ?? "")}
                </div>
                <div className="whitespace-pre-wrap">{String(m.body)}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <Input
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              placeholder="Reply as platform…"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendReply();
                }
              }}
            />
            <Button onClick={() => void sendReply()} disabled={sending || !reply.trim()}>
              {sending ? "Sending…" : "Send"}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
'''

ACTIVITY_PLATFORM = r'''"use client";

import {
  DataTable,
  EmptyState,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@finance-os/ui";
import { PlatformGoldenRuleBanner } from "@/components/platform-operator/PlatformShell";
import { usePlatformActivity } from "@/hooks/use-platform-operator";
import { mapPlatformOperatorErrorToUserMessage } from "@/lib/platform-operator";

export default function PlatformActivityPage() {
  const query = usePlatformActivity();
  if (query.isLoading) return <LoadingSkeleton rows={8} />;

  const items = (query.data ?? []) as Array<Record<string, unknown>>;
  const errMsg = query.error
    ? mapPlatformOperatorErrorToUserMessage(
        (query.error as { status?: number }).status ?? 500,
        query.error,
      )
    : null;

  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "when", header: "When", cell: (r) => String(r.created_at ?? "—") },
    {
      id: "org",
      header: "Org",
      cell: (r) => <code className="text-xs">{String(r.org_id ?? "—").slice(0, 8)}</code>,
    },
    { id: "action", header: "Action", cell: (r) => String(r.action ?? "—") },
    {
      id: "entity",
      header: "Entity",
      cell: (r) => `${r.entity_type ?? ""} ${r.entity_id ?? ""}`.trim() || "—",
    },
    { id: "summary", header: "Summary", cell: (r) => String(r.summary ?? "—") },
    { id: "actor", header: "Actor", cell: (r) => String(r.actor_type ?? "—") },
  ];

  return (
    <div>
      <PageHeader
        title="Activity"
        description="Cross-tenant product activity (mutations / deletes) from GET /ops/platform/activity"
      />
      <PlatformGoldenRuleBanner />
      {errMsg ? <p className="mb-3 text-sm text-destructive">{errMsg}</p> : null}
      {items.length === 0 ? (
        <EmptyState
          title="No activity yet"
          description="Mutating API calls write activity after migration 088."
        />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r, i) => String(r.id ?? i)} />
      )}
    </div>
  );
}
'''

RECYCLE_PLATFORM = r'''"use client";

import { useState } from "react";
import {
  Button,
  DataTable,
  EmptyState,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@finance-os/ui";
import { PlatformGoldenRuleBanner } from "@/components/platform-operator/PlatformShell";
import { useApi } from "@/hooks/use-api";
import { usePlatformRecycleBin } from "@/hooks/use-platform-operator";
import {
  mapPlatformOperatorErrorToUserMessage,
  restorePlatformRecycleItem,
} from "@/lib/platform-operator";
import { useQueryClient } from "@tanstack/react-query";

export default function PlatformRecycleBinPage() {
  const query = usePlatformRecycleBin();
  const { api } = useApi();
  const qc = useQueryClient();
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  if (query.isLoading) return <LoadingSkeleton rows={8} />;
  const items = (query.data ?? []) as Array<Record<string, unknown>>;
  const listErr = query.error
    ? mapPlatformOperatorErrorToUserMessage(
        (query.error as { status?: number }).status ?? 500,
        query.error,
      )
    : null;

  async function restore(id: string) {
    setErr(null);
    setBusyId(id);
    try {
      await restorePlatformRecycleItem(api, id);
      qc.invalidateQueries({ queryKey: ["platform-operator", "recycle"] });
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    } finally {
      setBusyId(null);
    }
  }

  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "when", header: "Deleted", cell: (r) => String(r.deleted_at ?? "—") },
    {
      id: "org",
      header: "Org",
      cell: (r) => <code className="text-xs">{String(r.org_id ?? "—").slice(0, 8)}</code>,
    },
    { id: "type", header: "Type", cell: (r) => String(r.entity_type ?? "—") },
    { id: "id", header: "Entity", cell: (r) => String(r.entity_id ?? "—") },
    { id: "reason", header: "Reason", cell: (r) => String(r.delete_reason ?? "—") },
    {
      id: "restore",
      header: "",
      cell: (r) => (
        <Button
          onClick={() => void restore(String(r.id))}
          disabled={busyId === String(r.id)}
        >
          {busyId === String(r.id) ? "Restoring…" : "Restore"}
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Recycle bin"
        description="Restore available entity snapshots (POST /ops/platform/recycle-bin/{id}/restore)"
      />
      <PlatformGoldenRuleBanner />
      {listErr || err ? <p className="mb-3 text-sm text-destructive">{listErr ?? err}</p> : null}
      {items.length === 0 ? (
        <EmptyState title="Empty" description="No available recycle entries for any org." />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r) => String(r.id)} />
      )}
    </div>
  );
}
'''

TENANT_SUPPORT = r'''"use client";

import { useState } from "react";
import {
  Button,
  DataTable,
  EmptyState,
  Input,
  Label,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@finance-os/ui";
import { useApi } from "@/hooks/use-api";
import {
  createSupportTicket,
  getSupportTicket,
  listSupportTickets,
  replySupportTicket,
} from "@/lib/control-plane/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";

export default function TenantSupportPage() {
  const { api, isReady } = useApi();
  const qc = useQueryClient();
  const tickets = useQuery({
    queryKey: ["support", "tickets"],
    enabled: isReady,
    queryFn: () => listSupportTickets(api),
  });
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [thread, setThread] = useState<Record<string, unknown> | null>(null);
  const [reply, setReply] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function createTicket(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSaving(true);
    try {
      await createSupportTicket(api, { subject: subject.trim(), body: body.trim() });
      setSubject("");
      setBody("");
      await qc.invalidateQueries({ queryKey: ["support", "tickets"] });
    } catch (ex) {
      setErr(String((ex as Error).message || ex));
    } finally {
      setSaving(false);
    }
  }

  async function open(id: string) {
    setSelected(id);
    setErr(null);
    try {
      setThread((await getSupportTicket(api, id)) as Record<string, unknown>);
    } catch (ex) {
      setErr(String((ex as Error).message || ex));
    }
  }

  async function send() {
    if (!selected || !reply.trim()) return;
    setSaving(true);
    try {
      await replySupportTicket(api, selected, reply.trim());
      setReply("");
      await open(selected);
    } catch (ex) {
      setErr(String((ex as Error).message || ex));
    } finally {
      setSaving(false);
    }
  }

  if (tickets.isLoading) return <LoadingSkeleton rows={6} />;
  const items = tickets.data ?? [];
  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "subject", header: "Subject", cell: (r) => String(r.subject ?? "—") },
    { id: "status", header: "Status", cell: (r) => String(r.status ?? "—") },
    {
      id: "open",
      header: "",
      cell: (r) => (
        <Button variant="outline" onClick={() => void open(String(r.id))}>
          Open
        </Button>
      ),
    },
  ];

  return (
    <div className="p-4">
      <PageHeader
        title="Support"
        description="Contact platform support about access, billing, or incidents"
      />
      {err || tickets.error ? (
        <p className="mb-2 text-sm text-destructive">
          {err ?? String((tickets.error as Error)?.message ?? tickets.error)}
        </p>
      ) : null}
      <form className="mb-6 max-w-lg space-y-2" onSubmit={(e) => void createTicket(e)}>
        <div className="space-y-1">
          <Label>Subject</Label>
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} required />
        </div>
        <div className="space-y-1">
          <Label>Message</Label>
          <Input value={body} onChange={(e) => setBody(e.target.value)} required />
        </div>
        <Button type="submit" disabled={saving}>
          {saving ? "Submitting…" : "Open ticket"}
        </Button>
      </form>
      {items.length === 0 ? (
        <EmptyState title="No tickets yet" description="Your org has not opened any support tickets." />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r) => String(r.id)} />
      )}
      {thread ? (
        <div className="mt-6 rounded-md border p-4">
          <div className="space-y-2 text-sm">
            {((thread.messages as Array<Record<string, unknown>>) ?? []).map((m) => (
              <div key={String(m.id)} className="rounded bg-muted/40 px-3 py-2">
                <div className="text-xs text-muted-foreground">{String(m.author_side)}</div>
                <div className="whitespace-pre-wrap">{String(m.body)}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <Input value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Reply…" />
            <Button onClick={() => void send()} disabled={saving || !reply.trim()}>
              Reply
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
'''

TENANT_ACTIVITY = r'''"use client";

import {
  DataTable,
  EmptyState,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@finance-os/ui";
import { useApi } from "@/hooks/use-api";
import { listTenantActivity } from "@/lib/control-plane/api";
import { useQuery } from "@tanstack/react-query";

export default function TenantActivityPage() {
  const { api, isReady } = useApi();
  const query = useQuery({
    queryKey: ["activity", "tenant"],
    enabled: isReady,
    queryFn: () => listTenantActivity(api),
  });
  if (query.isLoading) return <LoadingSkeleton rows={6} />;
  const items = query.data ?? [];
  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "when", header: "When", cell: (r) => String(r.created_at ?? "—") },
    { id: "action", header: "Action", cell: (r) => String(r.action ?? "—") },
    {
      id: "entity",
      header: "Entity",
      cell: (r) => `${r.entity_type ?? ""} ${r.entity_id ?? ""}`.trim() || "—",
    },
    { id: "summary", header: "Summary", cell: (r) => String(r.summary ?? "—") },
  ];
  return (
    <div className="p-4">
      <PageHeader
        title="Activity"
        description="Recent mutations and deletes in your organization (GET /activity)"
      />
      {query.error ? (
        <p className="mb-2 text-sm text-destructive">{String((query.error as Error).message)}</p>
      ) : null}
      {items.length === 0 ? (
        <EmptyState title="No activity" description="Product activity will appear here." />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r, i) => String(r.id ?? i)} />
      )}
    </div>
  );
}
'''

TENANT_RECYCLE = r'''"use client";

import {
  Button,
  DataTable,
  EmptyState,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@finance-os/ui";
import { useApi } from "@/hooks/use-api";
import { listTenantRecycle, restoreTenantRecycle } from "@/lib/control-plane/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

export default function TenantRecyclePage() {
  const { api, isReady } = useApi();
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["recycle", "tenant"],
    enabled: isReady,
    queryFn: () => listTenantRecycle(api),
  });
  if (query.isLoading) return <LoadingSkeleton rows={6} />;
  const items = query.data ?? [];
  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "when", header: "Deleted", cell: (r) => String(r.deleted_at ?? "—") },
    { id: "type", header: "Type", cell: (r) => String(r.entity_type ?? "—") },
    { id: "entity", header: "Entity", cell: (r) => String(r.entity_id ?? "—") },
    {
      id: "restore",
      header: "",
      cell: (r) => (
        <Button
          disabled={busy === String(r.id)}
          onClick={async () => {
            setBusy(String(r.id));
            try {
              await restoreTenantRecycle(api, String(r.id));
              await qc.invalidateQueries({ queryKey: ["recycle", "tenant"] });
            } finally {
              setBusy(null);
            }
          }}
        >
          {busy === String(r.id) ? "Restoring…" : "Restore"}
        </Button>
      ),
    },
  ];
  return (
    <div className="p-4">
      <PageHeader
        title="Recycle bin"
        description="Restore available deleted records for your organization"
      />
      {query.error ? (
        <p className="mb-2 text-sm text-destructive">{String((query.error as Error).message)}</p>
      ) : null}
      {items.length === 0 ? (
        <EmptyState title="Empty" description="No items available to restore." />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r) => String(r.id)} />
      )}
    </div>
  );
}
'''


def write(rel: str, content: str) -> None:
    p = FE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print("wrote", p)


def main() -> None:
    patch_nav()
    patch_api()
    patch_hooks()
    write("app/(platform)/platform/features/page.tsx", FEATURES_PAGE)
    write("app/(platform)/platform/support/page.tsx", SUPPORT_PLATFORM)
    write("app/(platform)/platform/activity/page.tsx", ACTIVITY_PLATFORM)
    write("app/(platform)/platform/recycle-bin/page.tsx", RECYCLE_PLATFORM)
    write("app/(workspace)/support/page.tsx", TENANT_SUPPORT)
    write("app/(admin)/admin/platform/activity/page.tsx", TENANT_ACTIVITY)
    write("app/(admin)/admin/platform/recycle-bin/page.tsx", TENANT_RECYCLE)

    # Re-export if needed
    index = FE / "lib" / "platform-operator" / "index.ts"
    # already export * from api

    # control-plane api typing fix for finance-os client
    cp = FE / "lib" / "control-plane" / "api.ts"
    if cp.exists():
        ct = cp.read_text(encoding="utf-8")
        if "@finance-os/api-client" not in ct:
            ct = 'import type { ApiClient } from "@finance-os/api-client";\n' + ct
            cp.write_text(ct, encoding="utf-8")

    # Regenerating screen preview after nav featureCode expands is optional
    print("done")


if __name__ == "__main__":
    main()
