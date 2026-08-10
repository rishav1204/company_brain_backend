"""Patch frontend platform control-plane files (FE lives outside backend workspace)."""
from __future__ import annotations

from pathlib import Path

FE = Path(r"D:\new-project-fe\apps\web\src")


def patch_nav_config() -> None:
    path = FE / "config" / "nav-config.ts"
    text = path.read_text(encoding="utf-8")
    if "featureCode?: string" not in text:
        text = text.replace(
            """export type NavItem = {
  label: string;
  href: string;
  permission?: string;
};""",
            """export type NavItem = {
  label: string;
  href: string;
  permission?: string;
  /** Billing / product feature code; when set, nav requires entitlement. */
  featureCode?: string;
};""",
        )

    old_ai = (
        '{ label: "Invoice AI", href: "/intelligence/invoice-ai", permission: "invoice.ai.review" },\n'
        '          { label: "Workflow intelligence", href: "/intelligence/workflow", permission: "workflow.read" },\n'
        '          { label: "Agents", href: "/intelligence/agents", permission: "agent.run" },\n'
        '          { label: "Memory", href: "/intelligence/memory", permission: "memory.read" },\n'
        '          { label: "Graph", href: "/intelligence/graph", permission: "graph.read" },\n'
        '          { label: "Forecasting", href: "/intelligence/forecasting", permission: "forecast.read" },'
    )
    new_ai = (
        '{ label: "Invoice AI", href: "/intelligence/invoice-ai", permission: "invoice.ai.review", featureCode: "invoice_ai" },\n'
        '          { label: "Workflow intelligence", href: "/intelligence/workflow", permission: "workflow.read", featureCode: "workflow_intelligence" },\n'
        '          { label: "Agents", href: "/intelligence/agents", permission: "agent.run", featureCode: "agents" },\n'
        '          { label: "Memory", href: "/intelligence/memory", permission: "memory.read", featureCode: "memory" },\n'
        '          { label: "Graph", href: "/intelligence/graph", permission: "graph.read", featureCode: "graph_engine" },\n'
        '          { label: "Forecasting", href: "/intelligence/forecasting", permission: "forecast.read", featureCode: "forecasting" },'
    )
    if 'featureCode: "invoice_ai"' not in text:
        text = text.replace(old_ai, new_ai)

    pairs = [
        ('href: "/accounting/coa", permission: "coa.read"', 'href: "/accounting/coa", permission: "coa.read", featureCode: "coa"'),
        ('href: "/accounting/journals", permission: "journal.read"', 'href: "/accounting/journals", permission: "journal.read", featureCode: "journals"'),
        ('href: "/accounting/journals/approval-queue", permission: "journal.approve"', 'href: "/accounting/journals/approval-queue", permission: "journal.approve", featureCode: "journals"'),
        ('href: "/accounting/gl/ledger", permission: "gl.read"', 'href: "/accounting/gl/ledger", permission: "gl.read", featureCode: "gl"'),
        ('href: "/accounting/gl/trial-balance", permission: "gl.read"', 'href: "/accounting/gl/trial-balance", permission: "gl.read", featureCode: "gl"'),
        ('href: "/accounting/vouchers", permission: "voucher.read"', 'href: "/accounting/vouchers", permission: "voucher.read", featureCode: "vouchers"'),
        ('href: "/operations/ap/vendors", permission: "ap.vendor.read"', 'href: "/operations/ap/vendors", permission: "ap.vendor.read", featureCode: "ap"'),
        ('href: "/operations/ap/invoices", permission: "ap.invoice.read"', 'href: "/operations/ap/invoices", permission: "ap.invoice.read", featureCode: "ap"'),
        ('href: "/operations/ap/payments", permission: "ap.payment.read"', 'href: "/operations/ap/payments", permission: "ap.payment.read", featureCode: "ap"'),
        ('href: "/operations/ap/aging", permission: "ap.invoice.read"', 'href: "/operations/ap/aging", permission: "ap.invoice.read", featureCode: "ap"'),
        ('href: "/operations/ar/customers", permission: "ar.customer.read"', 'href: "/operations/ar/customers", permission: "ar.customer.read", featureCode: "ar"'),
        ('href: "/operations/ar/invoices", permission: "ar.invoice.read"', 'href: "/operations/ar/invoices", permission: "ar.invoice.read", featureCode: "ar"'),
        ('href: "/operations/ar/collections", permission: "ar.collection.manage"', 'href: "/operations/ar/collections", permission: "ar.collection.manage", featureCode: "ar"'),
        ('href: "/operations/ar/aging", permission: "ar.invoice.read"', 'href: "/operations/ar/aging", permission: "ar.invoice.read", featureCode: "ar"'),
        ('href: "/operations/procurement/pr", permission: "procurement.read"', 'href: "/operations/procurement/pr", permission: "procurement.read", featureCode: "procurement"'),
        ('href: "/operations/procurement/po", permission: "procurement.read"', 'href: "/operations/procurement/po", permission: "procurement.read", featureCode: "procurement"'),
        ('href: "/operations/procurement/grn", permission: "procurement.read"', 'href: "/operations/procurement/grn", permission: "procurement.read", featureCode: "procurement"'),
        ('href: "/operations/procurement/matches", permission: "procurement.read"', 'href: "/operations/procurement/matches", permission: "procurement.read", featureCode: "procurement"'),
        ('href: "/operations/procurement/analytics", permission: "procurement.read"', 'href: "/operations/procurement/analytics", permission: "procurement.read", featureCode: "procurement"'),
        ('href: "/operations/expenses/claims", permission: "expense.read"', 'href: "/operations/expenses/claims", permission: "expense.read", featureCode: "expense"'),
        ('href: "/operations/expenses/advances", permission: "expense.read"', 'href: "/operations/expenses/advances", permission: "expense.read", featureCode: "expense"'),
        ('href: "/operations/expenses/policies", permission: "expense.read"', 'href: "/operations/expenses/policies", permission: "expense.read", featureCode: "expense"'),
        ('href: "/operations/expenses/analytics", permission: "expense.read"', 'href: "/operations/expenses/analytics", permission: "expense.read", featureCode: "expense"'),
        ('href: "/governance/audit", permission: "audit.read"', 'href: "/governance/audit", permission: "audit.read", featureCode: "audit_explorer"'),
    ]
    for a, b in pairs:
        if b not in text:
            text = text.replace(a, b)

    needle = '{ label: "Violations", href: "/governance/violations", permission: "audit.read" },'
    if 'href: "/support"' not in text and needle in text:
        text = text.replace(
            needle,
            needle
            + "\n"
            + '          { label: "Activity", href: "/admin/platform/activity", permission: "audit.read" },\n'
            + '          { label: "Recycle bin", href: "/admin/platform/recycle-bin", permission: "audit.read" },\n'
            + '          { label: "Support", href: "/support", permission: "organization.manage" },',
        )

    if "hasFeature?:" not in text:
        text = text.replace(
            """function itemAllowed(item: NavItem, hasPermission: (key: string) => boolean): boolean {
  if (!item.permission) return true;
  if (hasPermission(item.permission)) return true;""",
            """function itemAllowed(
  item: NavItem,
  hasPermission: (key: string) => boolean,
  hasFeature?: (featureCode: string) => boolean,
): boolean {
  if (item.featureCode && hasFeature && !hasFeature(item.featureCode)) {
    return false;
  }
  if (!item.permission) return true;
  if (hasPermission(item.permission)) return true;""",
        )
        text = text.replace(
            """export function filterNavByPermissions(
  categories: NavCategory[],
  hasPermission: (key: string) => boolean,
): NavCategory[] {
  return categories
    .map((cat) => ({
      ...cat,
      subCategories: cat.subCategories
        .map((sub) => ({
          ...sub,
          items: sub.items.filter((item) => itemAllowed(item, hasPermission)),
        }))
        .filter((sub) => sub.items.length > 0),
    }))
    .filter((cat) => cat.subCategories.length > 0);
}""",
            """export function filterNavByPermissions(
  categories: NavCategory[],
  hasPermission: (key: string) => boolean,
  hasFeature?: (featureCode: string) => boolean,
): NavCategory[] {
  return categories
    .map((cat) => ({
      ...cat,
      subCategories: cat.subCategories
        .map((sub) => ({
          ...sub,
          items: sub.items.filter((item) => itemAllowed(item, hasPermission, hasFeature)),
        }))
        .filter((sub) => sub.items.length > 0),
    }))
    .filter((cat) => cat.subCategories.length > 0);
}""",
        )
    path.write_text(text, encoding="utf-8")
    print("patched", path)


def patch_sidenav() -> None:
    path = FE / "components" / "shell" / "SideNav.tsx"
    text = path.read_text(encoding="utf-8")
    if "useBillingEntitlements" not in text:
        text = text.replace(
            'import { useAuth } from "@/providers/auth-provider";',
            'import { useAuth } from "@/providers/auth-provider";\n'
            'import { useBillingEntitlements } from "@/hooks/use-billing";',
        )
        text = text.replace(
            """  const { hasPermission } = useAuth();
  const openTab = useTabStore((s) => s.openTab);
  const categories = React.useMemo(
    () => filterNavByPermissions(NAV_CONFIG, hasPermission),
    [hasPermission],
  );""",
            """  const { hasPermission } = useAuth();
  const entitlements = useBillingEntitlements();
  const openTab = useTabStore((s) => s.openTab);
  const hasFeature = React.useCallback(
    (code: string) => {
      const features = entitlements.data?.features ?? entitlements.data?.entitlements ?? [];
      // Until entitlements load, show all feature-gated items (permission still applies).
      if (!entitlements.data) return true;
      const match = features.find((f: { feature_code?: string; enabled?: boolean }) => f.feature_code === code);
      return match?.enabled === true;
    },
    [entitlements.data],
  );
  const categories = React.useMemo(
    () => filterNavByPermissions(NAV_CONFIG, hasPermission, hasFeature),
    [hasPermission, hasFeature],
  );""",
        )
        path.write_text(text, encoding="utf-8")
        print("patched", path)
    else:
        print("sidenav already patched")


def patch_platform_shell() -> None:
    path = FE / "components" / "platform-operator" / "PlatformShell.tsx"
    text = path.read_text(encoding="utf-8")
    if "/platform/features" not in text:
        text = text.replace(
            """  { href: "/platform/commercial", label: "Commercial" },
  { href: "/platform/ops/queues", label: "Queues" },""",
            """  { href: "/platform/commercial", label: "Commercial" },
  { href: "/platform/features", label: "Features" },
  { href: "/platform/support", label: "Support" },
  { href: "/platform/activity", label: "Activity" },
  { href: "/platform/recycle-bin", label: "Recycle bin" },
  { href: "/platform/ops/queues", label: "Queues" },""",
        )
        path.write_text(text, encoding="utf-8")
        print("patched", path)
    else:
        print("shell already patched")


def append_api_methods() -> None:
    path = FE / "lib" / "platform-operator" / "api.ts"
    text = path.read_text(encoding="utf-8")
    if "disableOrgAi" in text:
        print("api already has control plane methods")
        return
    extra = '''

/* ── Control plane (plans extended + access/support/activity/recycle) ─ */

export async function getAdminBillingPlan(api: ApiClient, planKey: string) {
  return operatorGet<{ plan: Record<string, unknown> }>(
    api,
    `${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}`,
  );
}

export async function createAdminBillingPlan(api: ApiClient, body: Record<string, unknown>) {
  return operatorPost(api, `${ADMIN_BILLING_PREFIX}/plans`, body, idemKey());
}

export async function updateAdminBillingPlan(
  api: ApiClient,
  planKey: string,
  body: Record<string, unknown>,
) {
  return operatorPost(
    api,
    `${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}`,
    body,
    idemKey(),
    "PATCH",
  ).catch(async () => {
    // operatorPost may only support POST; use api client directly if needed
    return (api as { request?: Function }).request
      ? (api as any).request("PATCH", `${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}`, body)
      : null;
  });
}

export async function replaceAdminPlanFeatures(
  api: ApiClient,
  planKey: string,
  features: Array<string | { feature_code: string; enabled?: boolean }>,
) {
  return (api as any).put
    ? (api as any).put(`${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}/features`, { features })
    : operatorPost(
        api,
        `${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}/features`,
        { features },
        idemKey(),
      );
}

export async function replaceAdminPlanLimits(
  api: ApiClient,
  planKey: string,
  limits: Array<{ limit_code: string; limit_value: number }>,
) {
  return (api as any).put
    ? (api as any).put(`${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}/limits`, { limits })
    : operatorPost(
        api,
        `${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}/limits`,
        { limits },
        idemKey(),
      );
}

export async function disableOrgAi(api: ApiClient, orgId: string) {
  return operatorPost(
    api,
    `${ADMIN_BILLING_PREFIX}/orgs/${encodeURIComponent(orgId)}/disable-ai`,
    {},
    idemKey(),
  );
}

export async function listPlatformFeatures(api: ApiClient) {
  const raw = await operatorGet<unknown>(api, "/ops/platform/features");
  return normalizeListResponse<Record<string, unknown>>(raw);
}

export async function getOrgControls(api: ApiClient, orgId: string) {
  return operatorGet<{ controls: Record<string, unknown> }>(
    api,
    `/ops/platform/orgs/${encodeURIComponent(orgId)}/controls`,
  );
}

export async function patchOrgControls(
  api: ApiClient,
  orgId: string,
  body: Record<string, unknown>,
) {
  return (api as any).patch
    ? (api as any).patch(`/ops/platform/orgs/${encodeURIComponent(orgId)}/controls`, body)
    : operatorPost(api, `/ops/platform/orgs/${encodeURIComponent(orgId)}/controls`, body, idemKey());
}

export async function listPlatformSupportTickets(
  api: ApiClient,
  params?: { org_id?: string; status?: string },
) {
  const suffix = buildQuery({ org_id: params?.org_id, status: params?.status, limit: 100 });
  const raw = await operatorGet<unknown>(api, `/ops/platform/support/tickets${suffix}`);
  return normalizeListResponse<Record<string, unknown>>(raw);
}

export async function getPlatformSupportTicket(api: ApiClient, ticketId: string) {
  return operatorGet<Record<string, unknown>>(
    api,
    `/ops/platform/support/tickets/${encodeURIComponent(ticketId)}`,
  );
}

export async function replyPlatformSupportTicket(
  api: ApiClient,
  ticketId: string,
  body: string,
) {
  return operatorPost(
    api,
    `/ops/platform/support/tickets/${encodeURIComponent(ticketId)}/messages`,
    { body },
    idemKey(),
  );
}

export async function listPlatformActivity(
  api: ApiClient,
  params?: { org_id?: string; action?: string },
) {
  const suffix = buildQuery({ org_id: params?.org_id, action: params?.action, limit: 100 });
  const raw = await operatorGet<unknown>(api, `/ops/platform/activity${suffix}`);
  return normalizeListResponse<Record<string, unknown>>(raw);
}

export async function listPlatformRecycleBin(api: ApiClient, params?: { org_id?: string }) {
  const suffix = buildQuery({ org_id: params?.org_id, limit: 100 });
  const raw = await operatorGet<unknown>(api, `/ops/platform/recycle-bin${suffix}`);
  return normalizeListResponse<Record<string, unknown>>(raw);
}

export async function restorePlatformRecycleItem(api: ApiClient, recycleId: string) {
  return operatorPost(
    api,
    `/ops/platform/recycle-bin/${encodeURIComponent(recycleId)}/restore`,
    {},
    idemKey(),
  );
}
'''
    # Prefer proper patch/put via raw fetch helper - check how operatorPost works
    path.write_text(text + extra, encoding="utf-8")
    print("appended api methods")


def fix_api_client_methods() -> None:
    """Ensure patch/put work via existing ApiClient patterns."""
    api_client = FE / "lib" / "api-client.ts"
    if not api_client.exists():
        # try alternate
        candidates = list(FE.rglob("api-client.ts")) + list(FE.rglob("ApiClient*.ts"))
        print("api client candidates", candidates[:5])
        return
    text = api_client.read_text(encoding="utf-8")
    print("api-client has patch", "patch(" in text or ".patch" in text)


def write_page(rel: str, content: str) -> None:
    path = FE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print("wrote", path)


def main() -> None:
    patch_nav_config()
    patch_sidenav()
    patch_platform_shell()
    append_api_methods()
    fix_api_client_methods()

    # Commercial page enhancement - write full replacement with plan editor + disable AI
    write_page(
        "app/(platform)/platform/commercial/page.tsx",
        COMMERCIAL_PAGE,
    )
    write_page("app/(platform)/platform/features/page.tsx", FEATURES_PAGE)
    write_page("app/(platform)/platform/orgs/[orgId]/controls/page.tsx", ORG_CONTROLS_PAGE)
    write_page("app/(platform)/platform/support/page.tsx", SUPPORT_PLATFORM_PAGE)
    write_page("app/(platform)/platform/activity/page.tsx", ACTIVITY_PLATFORM_PAGE)
    write_page("app/(platform)/platform/recycle-bin/page.tsx", RECYCLE_PLATFORM_PAGE)
    write_page("app/(app)/support/page.tsx", SUPPORT_TENANT_PAGE)
    write_page("app/(admin)/admin/platform/activity/page.tsx", ACTIVITY_TENANT_PAGE)
    write_page("app/(admin)/admin/platform/recycle-bin/page.tsx", RECYCLE_TENANT_PAGE)

    # Hook extensions
    hooks = FE / "hooks" / "use-platform-operator.ts"
    ht = hooks.read_text(encoding="utf-8")
    if "useDisableOrgAi" not in ht:
        ht = ht.replace(
            '  setPlatformUserStatus,\n} from "@/lib/platform-operator";',
            '  setPlatformUserStatus,\n  disableOrgAi,\n  listPlatformFeatures,\n  getOrgControls,\n  patchOrgControls,\n  listPlatformSupportTickets,\n  getPlatformSupportTicket,\n  replyPlatformSupportTicket,\n  listPlatformActivity,\n  listPlatformRecycleBin,\n  restorePlatformRecycleItem,\n  createAdminBillingPlan,\n  getAdminBillingPlan,\n  replaceAdminPlanFeatures,\n  replaceAdminPlanLimits,\n} from "@/lib/platform-operator";',
        )
        if "disableOrgAi" not in ht:
            # imports may already be multi-line - append import block end
            ht = ht.replace(
                '} from "@/lib/platform-operator";',
                """  disableOrgAi,
  listPlatformFeatures,
  getOrgControls,
  patchOrgControls,
  listPlatformSupportTickets,
  getPlatformSupportTicket,
  replyPlatformSupportTicket,
  listPlatformActivity,
  listPlatformRecycleBin,
  restorePlatformRecycleItem,
  createAdminBillingPlan,
  getAdminBillingPlan,
  replaceAdminPlanFeatures,
  replaceAdminPlanLimits,
} from "@/lib/platform-operator";""",
                1,
            )
        ht += '''

export function useDisableOrgAi() {
  const { api } = useApi();
  return useMutation({
    mutationFn: (orgId: string) => disableOrgAi(api, orgId),
  });
}

export function usePlatformFeatures(enabled = true) {
  const { api, isReady } = useApi();
  return useQuery({
    queryKey: [...queryKeys.platformOperator.orgs(), "features"],
    enabled: isReady && enabled,
    queryFn: () => listPlatformFeatures(api),
  });
}

export function useOrgControls(orgId: string, enabled = true) {
  const { api, isReady } = useApi();
  return useQuery({
    queryKey: ["platform-operator", "org-controls", orgId],
    enabled: isReady && enabled && !!orgId,
    queryFn: () => getOrgControls(api, orgId),
  });
}

export function usePatchOrgControls() {
  const { api } = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, body }: { orgId: string; body: Record<string, unknown> }) =>
      patchOrgControls(api, orgId, body),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["platform-operator", "org-controls", vars.orgId] });
    },
  });
}

export function usePlatformSupportTickets(enabled = true) {
  const { api, isReady } = useApi();
  return useQuery({
    queryKey: ["platform-operator", "support"],
    enabled: isReady && enabled,
    queryFn: () => listPlatformSupportTickets(api),
  });
}

export function usePlatformActivity(enabled = true) {
  const { api, isReady } = useApi();
  return useQuery({
    queryKey: ["platform-operator", "activity"],
    enabled: isReady && enabled,
    queryFn: () => listPlatformActivity(api),
  });
}

export function usePlatformRecycleBin(enabled = true) {
  const { api, isReady } = useApi();
  return useQuery({
    queryKey: ["platform-operator", "recycle"],
    enabled: isReady && enabled,
    queryFn: () => listPlatformRecycleBin(api),
  });
}

export function useCreateAdminPlan() {
  const { api } = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => createAdminBillingPlan(api, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.platformOperator.adminPlans() });
    },
  });
}

export function useReplacePlanFeatures() {
  const { api } = useApi();
  return useMutation({
    mutationFn: ({
      planKey,
      features,
    }: {
      planKey: string;
      features: Array<string | { feature_code: string; enabled?: boolean }>;
    }) => replaceAdminPlanFeatures(api, planKey, features),
  });
}
'''
        hooks.write_text(ht, encoding="utf-8")
        print("patched hooks")

    # types break_glass
    types = FE / "lib" / "platform-operator" / "types.ts"
    tt = types.read_text(encoding="utf-8")
    if "break_glass" not in tt:
        tt = tt.replace(
            """export type PlatformEntitlementOverrideInput = {
  org_id: string;
  feature_code: string;
  enabled: boolean;
  expires_at?: string;
};""",
            """export type PlatformEntitlementOverrideInput = {
  org_id: string;
  feature_code: string;
  enabled: boolean;
  break_glass?: boolean;
  expires_at?: string;
};""",
        )
        types.write_text(tt, encoding="utf-8")

    # query keys
    qk = FE / "lib" / "query-keys.ts"
    qt = qk.read_text(encoding="utf-8")
    if "features:" not in qt.split("platformOperator")[-1]:
        qt = qt.replace(
            "adminPlans: () => [\"platform-operator\", \"adminPlans\"] as const,",
            """adminPlans: () => ["platform-operator", "adminPlans"] as const,
    features: () => ["platform-operator", "features"] as const,
    support: () => ["platform-operator", "support"] as const,
    activity: () => ["platform-operator", "activity"] as const,
    recycle: () => ["platform-operator", "recycle"] as const,""",
        )
        qk.write_text(qt, encoding="utf-8")

    # tenant API helpers file
    write_page(
        "lib/control-plane/api.ts",
        CONTROL_PLANE_TENANT_API,
    )


COMMERCIAL_PAGE = r'''"use client";

import { useState } from "react";
import {
  Button,
  DataTable,
  EmptyState,
  Input,
  Label,
  LoadingSkeleton,
  PageHeader,
  Select,
  type DataTableColumn,
} from "@finance-os/ui";
import { Modal } from "@/components/patterns/Modal";
import { PlatformGoldenRuleBanner } from "@/components/platform-operator/PlatformShell";
import { mapPlatformOperatorErrorToUserMessage } from "@/lib/platform-operator";
import type { BillingPlan } from "@/lib/billing";
import {
  useAssignPlatformPlan,
  useCreateAdminPlan,
  useDisableOrgAi,
  useGrantPlatformCredits,
  useOverridePlatformEntitlement,
  usePlatformAdminPlans,
  usePlatformOrgs,
  useReplacePlanFeatures,
} from "@/hooks/use-platform-operator";

export default function PlatformCommercialPage() {
  const plansQuery = usePlatformAdminPlans();
  const orgsQuery = usePlatformOrgs();
  const [assignOpen, setAssignOpen] = useState(false);
  const [grantOpen, setGrantOpen] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [disableOpen, setDisableOpen] = useState(false);

  const plans = plansQuery.data ?? [];
  const orgs = orgsQuery.data?.items ?? [];
  const orgOptions = orgs.map((o) => ({
    value: o.id,
    label: `${o.name ?? o.org_name ?? o.id} (${o.id.slice(0, 8)}…)`,
  }));

  const columns: DataTableColumn<BillingPlan>[] = [
    { id: "key", header: "Plan key", cell: (r) => <code className="text-xs">{r.plan_key}</code> },
    { id: "name", header: "Name", cell: (r) => r.name ?? r.plan_name ?? "—" },
    {
      id: "credits",
      header: "AI credits / mo",
      cell: (r) => (r.monthly_ai_credits != null ? String(r.monthly_ai_credits) : "—"),
    },
    {
      id: "status",
      header: "Status",
      cell: (r) => r.status ?? "active",
    },
  ];

  if (plansQuery.isLoading || orgsQuery.isLoading) return <LoadingSkeleton rows={8} />;

  const err = plansQuery.error ?? orgsQuery.error;
  const errMsg = err
    ? mapPlatformOperatorErrorToUserMessage((err as { status?: number }).status ?? 500, err)
    : null;

  return (
    <div>
      <PageHeader
        title="Commercial control"
        description="Plan product CRUD, assign, AI credits, entitlements, and bulk Disable AI"
      />
      <PlatformGoldenRuleBanner />
      {errMsg ? <p className="mb-4 text-sm text-destructive">{errMsg}</p> : null}

      <div className="mb-6 flex flex-wrap gap-2">
        <Button onClick={() => setPlanOpen(true)}>Create plan</Button>
        <Button onClick={() => setAssignOpen(true)}>Assign plan</Button>
        <Button variant="outline" onClick={() => setGrantOpen(true)}>
          Grant credits
        </Button>
        <Button variant="outline" onClick={() => setOverrideOpen(true)}>
          Override entitlement
        </Button>
        <Button variant="outline" onClick={() => setDisableOpen(true)}>
          Disable AI for org
        </Button>
      </div>

      {plans.length === 0 ? (
        <EmptyState title="No plans" description="Admin plan catalog is empty." />
      ) : (
        <DataTable data={plans} columns={columns} getRowId={(r) => r.id ?? r.plan_key} />
      )}

      <PlanEditorDialog open={planOpen} onClose={() => setPlanOpen(false)} />
      <AssignDialog
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        plans={plans}
        orgOptions={orgOptions}
      />
      <GrantDialog open={grantOpen} onClose={() => setGrantOpen(false)} orgOptions={orgOptions} />
      <OverrideDialog
        open={overrideOpen}
        onClose={() => setOverrideOpen(false)}
        orgOptions={orgOptions}
      />
      <DisableAiDialog open={disableOpen} onClose={() => setDisableOpen(false)} orgOptions={orgOptions} />
    </div>
  );
}

function PlanEditorDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateAdminPlan();
  const replaceFeatures = useReplacePlanFeatures();
  const [planKey, setPlanKey] = useState("");
  const [name, setName] = useState("");
  const [tier, setTier] = useState("1");
  const [price, setPrice] = useState("0");
  const [credits, setCredits] = useState("0");
  const [featuresCsv, setFeaturesCsv] = useState("ap,ar,coa,gl,journals");
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const features = featuresCsv
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((feature_code) => ({ feature_code, enabled: true }));
      await create.mutateAsync({
        plan_key: planKey.trim(),
        name: name.trim() || planKey.trim(),
        tier: Number(tier) || 1,
        monthly_price_inr: Number(price) || 0,
        included_ai_credits: Number(credits) || 0,
        features,
      });
      if (features.length) {
        await replaceFeatures.mutateAsync({ planKey: planKey.trim(), features }).catch(() => null);
      }
      onClose();
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Create plan product">
      <form className="space-y-3" onSubmit={submit}>
        <div className="space-y-1">
          <Label>Plan key</Label>
          <Input value={planKey} onChange={(e) => setPlanKey(e.target.value)} required />
        </div>
        <div className="space-y-1">
          <Label>Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div className="space-y-1">
            <Label>Tier</Label>
            <Input type="number" min={1} value={tier} onChange={(e) => setTier(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Price INR</Label>
            <Input type="number" min={0} value={price} onChange={(e) => setPrice(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>AI credits / mo</Label>
            <Input type="number" min={0} value={credits} onChange={(e) => setCredits(e.target.value)} />
          </div>
        </div>
        <div className="space-y-1">
          <Label>Features (comma-separated codes)</Label>
          <Input value={featuresCsv} onChange={(e) => setFeaturesCsv(e.target.value)} />
        </div>
        {err ? <p className="text-sm text-destructive">{err}</p> : null}
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Creating…" : "Create plan"}
        </Button>
      </form>
    </Modal>
  );
}

function DisableAiDialog({
  open,
  onClose,
  orgOptions,
}: {
  open: boolean;
  onClose: () => void;
  orgOptions: { value: string; label: string }[];
}) {
  const disableAi = useDisableOrgAi();
  const [orgId, setOrgId] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!orgId) {
      setErr("Organization required");
      return;
    }
    try {
      await disableAi.mutateAsync(orgId);
      onClose();
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Disable AI for organization">
      <form className="space-y-3" onSubmit={submit}>
        <p className="text-sm text-muted-foreground">
          Turns off invoice_ai, agents, memory, graph_engine, workflow_intelligence, and forecasting for
          the org via entitlement overrides.
        </p>
        <div className="space-y-1">
          <Label>Organization</Label>
          <Select value={orgId} onChange={setOrgId} options={orgOptions} placeholder="Select org…" />
        </div>
        {err ? <p className="text-sm text-destructive">{err}</p> : null}
        <Button type="submit" disabled={disableAi.isPending}>
          {disableAi.isPending ? "Disabling…" : "Disable AI"}
        </Button>
      </form>
    </Modal>
  );
}

function AssignDialog({
  open,
  onClose,
  plans,
  orgOptions,
}: {
  open: boolean;
  onClose: () => void;
  plans: BillingPlan[];
  orgOptions: { value: string; label: string }[];
}) {
  const assign = useAssignPlatformPlan();
  const [orgId, setOrgId] = useState("");
  const [planKey, setPlanKey] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!orgId || !planKey) {
      setErr("Organization and plan are required");
      return;
    }
    try {
      await assign.mutateAsync({ org_id: orgId, plan_key: planKey });
      onClose();
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Assign plan to org">
      <form className="space-y-3" onSubmit={submit}>
        <div className="space-y-1">
          <Label>Organization</Label>
          <Select value={orgId} onChange={setOrgId} options={orgOptions} placeholder="Select org…" />
        </div>
        <div className="space-y-1">
          <Label>Plan</Label>
          <Select
            value={planKey}
            onChange={setPlanKey}
            options={plans.map((p) => ({
              value: p.plan_key,
              label: `${p.name ?? p.plan_key} (${p.plan_key})`,
            }))}
            placeholder="Select plan…"
          />
        </div>
        {err ? <p className="text-sm text-destructive">{err}</p> : null}
        <Button type="submit" disabled={assign.isPending}>
          {assign.isPending ? "Assigning…" : "Assign"}
        </Button>
      </form>
    </Modal>
  );
}

function GrantDialog({
  open,
  onClose,
  orgOptions,
}: {
  open: boolean;
  onClose: () => void;
  orgOptions: { value: string; label: string }[];
}) {
  const grant = useGrantPlatformCredits();
  const [orgId, setOrgId] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const n = Number(amount);
    if (!orgId || !n || n <= 0) {
      setErr("Org and positive amount required");
      return;
    }
    try {
      await grant.mutateAsync({ org_id: orgId, amount: n, reason: reason || undefined });
      onClose();
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Grant AI credits">
      <form className="space-y-3" onSubmit={submit}>
        <div className="space-y-1">
          <Label>Organization</Label>
          <Select value={orgId} onChange={setOrgId} options={orgOptions} placeholder="Select org…" />
        </div>
        <div className="space-y-1">
          <Label>Amount</Label>
          <Input type="number" min={1} value={amount} onChange={(e) => setAmount(e.target.value)} required />
        </div>
        <div className="space-y-1">
          <Label>Reason</Label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        {err ? <p className="text-sm text-destructive">{err}</p> : null}
        <Button type="submit" disabled={grant.isPending}>
          {grant.isPending ? "Granting…" : "Grant"}
        </Button>
      </form>
    </Modal>
  );
}

function OverrideDialog({
  open,
  onClose,
  orgOptions,
}: {
  open: boolean;
  onClose: () => void;
  orgOptions: { value: string; label: string }[];
}) {
  const override = useOverridePlatformEntitlement();
  const [orgId, setOrgId] = useState("");
  const [featureCode, setFeatureCode] = useState("");
  const [enabled, setEnabled] = useState("true");
  const [breakGlass, setBreakGlass] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!orgId || !featureCode.trim()) {
      setErr("Org and feature code required");
      return;
    }
    try {
      await override.mutateAsync({
        org_id: orgId,
        feature_code: featureCode.trim(),
        enabled: enabled === "true",
        break_glass: breakGlass,
      });
      onClose();
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Override entitlement">
      <form className="space-y-3" onSubmit={submit}>
        <div className="space-y-1">
          <Label>Organization</Label>
          <Select value={orgId} onChange={setOrgId} options={orgOptions} placeholder="Select org…" />
        </div>
        <div className="space-y-1">
          <Label>Feature code</Label>
          <Input value={featureCode} onChange={(e) => setFeatureCode(e.target.value)} required />
        </div>
        <div className="space-y-1">
          <Label>Enabled</Label>
          <Select
            value={enabled}
            onChange={setEnabled}
            options={[
              { value: "true", label: "Enabled" },
              { value: "false", label: "Disabled" },
            ]}
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={breakGlass} onChange={(e) => setBreakGlass(e.target.checked)} />
          Break-glass (grant above plan ceiling)
        </label>
        {err ? <p className="text-sm text-destructive">{err}</p> : null}
        <Button type="submit" disabled={override.isPending}>
          {override.isPending ? "Saving…" : "Save"}
        </Button>
      </form>
    </Modal>
  );
}
'''

FEATURES_PAGE = r'''"use client";

import Link from "next/link";
import {
  DataTable,
  EmptyState,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@finance-os/ui";
import { PlatformGoldenRuleBanner } from "@/components/platform-operator/PlatformShell";
import { usePlatformFeatures, usePlatformOrgs } from "@/hooks/use-platform-operator";

export default function PlatformFeaturesPage() {
  const featuresQuery = usePlatformFeatures();
  const orgsQuery = usePlatformOrgs();

  if (featuresQuery.isLoading) return <LoadingSkeleton rows={8} />;

  const items = (featuresQuery.data ?? []) as Array<Record<string, unknown>>;
  const orgs = orgsQuery.data?.items ?? [];

  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "code", header: "Code", cell: (r) => <code className="text-xs">{String(r.feature_code)}</code> },
    { id: "name", header: "Name", cell: (r) => String(r.name ?? "—") },
    { id: "category", header: "Category", cell: (r) => String(r.category ?? "—") },
    { id: "ai", header: "AI", cell: (r) => (r.is_ai ? "yes" : "no") },
    { id: "status", header: "Status", cell: (r) => String(r.status ?? "active") },
  ];

  return (
    <div>
      <PageHeader
        title="Feature catalog"
        description="Product feature codes used by plans, entitlements, nav, and org controls"
      />
      <PlatformGoldenRuleBanner />
      {items.length === 0 ? (
        <EmptyState title="No features" description="Run migration 088 to seed feature_catalog." />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r) => String(r.feature_code)} />
      )}
      <div className="mt-8">
        <h2 className="mb-2 text-sm font-medium">Org control shortcuts</h2>
        <ul className="space-y-1 text-sm">
          {orgs.slice(0, 20).map((o) => (
            <li key={o.id}>
              <Link className="text-primary underline" href={`/platform/orgs/${o.id}/controls`}>
                {o.name ?? o.org_name ?? o.id}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
'''

ORG_CONTROLS_PAGE = r'''"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Input, Label, LoadingSkeleton, PageHeader, Select } from "@finance-os/ui";
import { PlatformGoldenRuleBanner } from "@/components/platform-operator/PlatformShell";
import { useOrgControls, usePatchOrgControls } from "@/hooks/use-platform-operator";
import { mapPlatformOperatorErrorToUserMessage } from "@/lib/platform-operator";

export default function OrgControlsPage() {
  const params = useParams();
  const orgId = String(params.orgId ?? "");
  const query = useOrgControls(orgId);
  const patch = usePatchOrgControls();
  const [form, setForm] = useState({
    lifecycle_status: "active",
    login_allowed: "true",
    ai_enabled: "true",
    erp_modules_enabled: "true",
    api_access_allowed: "true",
    support_priority: "standard",
    notes: "",
  });
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const c = (query.data as { controls?: Record<string, unknown> } | undefined)?.controls;
    if (!c) return;
    setForm({
      lifecycle_status: String(c.lifecycle_status ?? "active"),
      login_allowed: c.login_allowed === false ? "false" : "true",
      ai_enabled: c.ai_enabled === false ? "false" : "true",
      erp_modules_enabled: c.erp_modules_enabled === false ? "false" : "true",
      api_access_allowed: c.api_access_allowed === false ? "false" : "true",
      support_priority: String(c.support_priority ?? "standard"),
      notes: String(c.notes ?? ""),
    });
  }, [query.data]);

  if (query.isLoading) return <LoadingSkeleton rows={8} />;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await patch.mutateAsync({
        orgId,
        body: {
          lifecycle_status: form.lifecycle_status,
          login_allowed: form.login_allowed === "true",
          ai_enabled: form.ai_enabled === "true",
          erp_modules_enabled: form.erp_modules_enabled === "true",
          api_access_allowed: form.api_access_allowed === "true",
          support_priority: form.support_priority,
          notes: form.notes || null,
        },
      });
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    }
  }

  return (
    <div>
      <PageHeader title="Org controls" description={`Emergency switches for ${orgId}`} />
      <PlatformGoldenRuleBanner />
      <form className="max-w-lg space-y-3" onSubmit={save}>
        <div className="space-y-1">
          <Label>Lifecycle</Label>
          <Select
            value={form.lifecycle_status}
            onChange={(v) => setForm((f) => ({ ...f, lifecycle_status: v }))}
            options={["active", "frozen", "suspended", "offboarding"].map((v) => ({
              value: v,
              label: v,
            }))}
          />
        </div>
        {(
          [
            ["login_allowed", "Login allowed"],
            ["ai_enabled", "AI enabled"],
            ["erp_modules_enabled", "ERP modules enabled"],
            ["api_access_allowed", "API access allowed"],
          ] as const
        ).map(([key, label]) => (
          <div key={key} className="space-y-1">
            <Label>{label}</Label>
            <Select
              value={form[key]}
              onChange={(v) => setForm((f) => ({ ...f, [key]: v }))}
              options={[
                { value: "true", label: "Yes" },
                { value: "false", label: "No" },
              ]}
            />
          </div>
        ))}
        <div className="space-y-1">
          <Label>Support priority</Label>
          <Select
            value={form.support_priority}
            onChange={(v) => setForm((f) => ({ ...f, support_priority: v }))}
            options={[
              { value: "standard", label: "Standard" },
              { value: "priority", label: "Priority" },
            ]}
          />
        </div>
        <div className="space-y-1">
          <Label>Notes</Label>
          <Input value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
        </div>
        {err ? <p className="text-sm text-destructive">{err}</p> : null}
        <Button type="submit" disabled={patch.isPending}>
          {patch.isPending ? "Saving…" : "Save controls"}
        </Button>
      </form>
    </div>
  );
}
'''

SUPPORT_PLATFORM_PAGE = r'''"use client";

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

export default function PlatformSupportPage() {
  const ticketsQuery = usePlatformSupportTickets();
  const { api } = useApi();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [thread, setThread] = useState<{ ticket?: Record<string, unknown>; messages?: Array<Record<string, unknown>> } | null>(null);
  const [reply, setReply] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const items = (ticketsQuery.data ?? []) as Array<Record<string, unknown>>;

  async function openTicket(id: string) {
    setSelectedId(id);
    setErr(null);
    try {
      const t = await getPlatformSupportTicket(api, id);
      setThread(t as typeof thread);
    } catch (error) {
      setErr(mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error));
    }
  }

  async function sendReply() {
    if (!selectedId || !reply.trim()) return;
    setErr(null);
    try {
      await replyPlatformSupportTicket(api, selectedId, reply.trim());
      setReply("");
      await openTicket(selectedId);
    } catch (error) {
      setErr(mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error));
    }
  }

  if (ticketsQuery.isLoading) return <LoadingSkeleton rows={8} />;

  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "subject", header: "Subject", cell: (r) => String(r.subject ?? "—") },
    { id: "org", header: "Org", cell: (r) => String(r.org_id ?? "—").slice(0, 8) },
    { id: "status", header: "Status", cell: (r) => String(r.status ?? "—") },
    {
      id: "open",
      header: "",
      cell: (r) => (
        <Button size="sm" variant="outline" onClick={() => openTicket(String(r.id))}>
          Open
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Support inbox" description="Cross-tenant support tickets" />
      <PlatformGoldenRuleBanner />
      {err ? <p className="mb-3 text-sm text-destructive">{err}</p> : null}
      {items.length === 0 ? (
        <EmptyState title="No tickets" description="Customer orgs can open tickets at /support." />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r) => String(r.id)} />
      )}
      {thread ? (
        <div className="mt-6 rounded-md border p-4">
          <h3 className="font-medium">{String(thread.ticket?.subject ?? selectedId)}</h3>
          <div className="mt-3 max-h-64 space-y-2 overflow-y-auto text-sm">
            {(thread.messages ?? []).map((m) => (
              <div key={String(m.id)} className="rounded bg-muted/40 px-3 py-2">
                <div className="text-xs text-muted-foreground">
                  {String(m.author_side)} · {String(m.created_at ?? "")}
                </div>
                <div>{String(m.body)}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <Input value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Reply…" />
            <Button onClick={sendReply}>Send</Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
'''

ACTIVITY_PLATFORM_PAGE = r'''"use client";

import {
  DataTable,
  EmptyState,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@finance-os/ui";
import { PlatformGoldenRuleBanner } from "@/components/platform-operator/PlatformShell";
import { usePlatformActivity } from "@/hooks/use-platform-operator";

export default function PlatformActivityPage() {
  const query = usePlatformActivity();
  if (query.isLoading) return <LoadingSkeleton rows={8} />;
  const items = (query.data ?? []) as Array<Record<string, unknown>>;
  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "when", header: "When", cell: (r) => String(r.created_at ?? "—") },
    { id: "org", header: "Org", cell: (r) => String(r.org_id ?? "—").slice(0, 8) },
    { id: "action", header: "Action", cell: (r) => String(r.action ?? "—") },
    { id: "entity", header: "Entity", cell: (r) => `${r.entity_type ?? ""} ${r.entity_id ?? ""}` },
    { id: "summary", header: "Summary", cell: (r) => String(r.summary ?? "—") },
  ];
  return (
    <div>
      <PageHeader title="Activity" description="Cross-tenant product activity feed" />
      <PlatformGoldenRuleBanner />
      {items.length === 0 ? (
        <EmptyState title="No activity" description="Mutating API calls will appear after migration 088." />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r, i) => String(r.id ?? i)} />
      )}
    </div>
  );
}
'''

RECYCLE_PLATFORM_PAGE = r'''"use client";

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
import { mapPlatformOperatorErrorToUserMessage, restorePlatformRecycleItem } from "@/lib/platform-operator";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

export default function PlatformRecycleBinPage() {
  const query = usePlatformRecycleBin();
  const { api } = useApi();
  const qc = useQueryClient();
  const [err, setErr] = useState<string | null>(null);
  if (query.isLoading) return <LoadingSkeleton rows={8} />;
  const items = (query.data ?? []) as Array<Record<string, unknown>>;

  async function restore(id: string) {
    setErr(null);
    try {
      await restorePlatformRecycleItem(api, id);
      qc.invalidateQueries({ queryKey: ["platform-operator", "recycle"] });
    } catch (error) {
      setErr(mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error));
    }
  }

  const columns: DataTableColumn<Record<string, unknown>>[] = [
    { id: "when", header: "Deleted", cell: (r) => String(r.deleted_at ?? "—") },
    { id: "org", header: "Org", cell: (r) => String(r.org_id ?? "—").slice(0, 8) },
    { id: "type", header: "Type", cell: (r) => String(r.entity_type ?? "—") },
    { id: "id", header: "Entity", cell: (r) => String(r.entity_id ?? "—") },
    {
      id: "restore",
      header: "",
      cell: (r) => (
        <Button size="sm" onClick={() => restore(String(r.id))}>
          Restore
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Recycle bin" description="Restore supported entity snapshots" />
      <PlatformGoldenRuleBanner />
      {err ? <p className="mb-3 text-sm text-destructive">{err}</p> : null}
      {items.length === 0 ? (
        <EmptyState title="Empty" description="No available recycle entries." />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r) => String(r.id)} />
      )}
    </div>
  );
}
'''

SUPPORT_TENANT_PAGE = r'''"use client";

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

  async function createTicket(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await createSupportTicket(api, { subject, body });
      setSubject("");
      setBody("");
      qc.invalidateQueries({ queryKey: ["support", "tickets"] });
    } catch (ex) {
      setErr(String((ex as Error).message || ex));
    }
  }

  async function open(id: string) {
    setSelected(id);
    setThread(await getSupportTicket(api, id));
  }

  async function send() {
    if (!selected || !reply.trim()) return;
    await replySupportTicket(api, selected, reply.trim());
    setReply("");
    await open(selected);
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
        <Button size="sm" variant="outline" onClick={() => open(String(r.id))}>
          Open
        </Button>
      ),
    },
  ];

  return (
    <div className="p-4">
      <PageHeader title="Support" description="Contact platform support about access, billing, or incidents" />
      {err ? <p className="mb-2 text-sm text-destructive">{err}</p> : null}
      <form className="mb-6 max-w-lg space-y-2" onSubmit={createTicket}>
        <div className="space-y-1">
          <Label>Subject</Label>
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} required />
        </div>
        <div className="space-y-1">
          <Label>Message</Label>
          <Input value={body} onChange={(e) => setBody(e.target.value)} required />
        </div>
        <Button type="submit">Open ticket</Button>
      </form>
      {items.length === 0 ? (
        <EmptyState title="No tickets yet" />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r) => String(r.id)} />
      )}
      {thread ? (
        <div className="mt-6 rounded-md border p-4">
          <div className="space-y-2 text-sm">
            {((thread.messages as Array<Record<string, unknown>>) ?? []).map((m) => (
              <div key={String(m.id)} className="rounded bg-muted/40 px-3 py-2">
                <div className="text-xs text-muted-foreground">{String(m.author_side)}</div>
                <div>{String(m.body)}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <Input value={reply} onChange={(e) => setReply(e.target.value)} />
            <Button onClick={send}>Reply</Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
'''

ACTIVITY_TENANT_PAGE = r'''"use client";

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
    { id: "summary", header: "Summary", cell: (r) => String(r.summary ?? "—") },
  ];
  return (
    <div className="p-4">
      <PageHeader title="Activity" description="Recent mutations and deletes in your organization" />
      {items.length === 0 ? (
        <EmptyState title="No activity" />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r, i) => String(r.id ?? i)} />
      )}
    </div>
  );
}
'''

RECYCLE_TENANT_PAGE = r'''"use client";

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

export default function TenantRecyclePage() {
  const { api, isReady } = useApi();
  const qc = useQueryClient();
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
          size="sm"
          onClick={async () => {
            await restoreTenantRecycle(api, String(r.id));
            qc.invalidateQueries({ queryKey: ["recycle", "tenant"] });
          }}
        >
          Restore
        </Button>
      ),
    },
  ];
  return (
    <div className="p-4">
      <PageHeader title="Recycle bin" description="Restore available deleted records" />
      {items.length === 0 ? (
        <EmptyState title="Empty" />
      ) : (
        <DataTable data={items} columns={columns} getRowId={(r) => String(r.id)} />
      )}
    </div>
  );
}
'''

CONTROL_PLANE_TENANT_API = r'''import type { ApiClient } from "@/lib/api-client";

function itemsOf(raw: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(raw)) return raw as Array<Record<string, unknown>>;
  if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    if (Array.isArray(o.items)) return o.items as Array<Record<string, unknown>>;
  }
  return [];
}

export async function listSupportTickets(api: ApiClient) {
  const raw = await api.get("/support/tickets");
  return itemsOf(raw);
}

export async function createSupportTicket(
  api: ApiClient,
  body: { subject: string; body: string; category?: string; priority?: string },
) {
  return api.post("/support/tickets", body);
}

export async function getSupportTicket(api: ApiClient, ticketId: string) {
  return api.get(`/support/tickets/${encodeURIComponent(ticketId)}`);
}

export async function replySupportTicket(api: ApiClient, ticketId: string, body: string) {
  return api.post(`/support/tickets/${encodeURIComponent(ticketId)}/messages`, { body });
}

export async function listTenantActivity(api: ApiClient) {
  const raw = await api.get("/activity");
  return itemsOf(raw);
}

export async function listTenantRecycle(api: ApiClient) {
  const raw = await api.get("/recycle-bin");
  return itemsOf(raw);
}

export async function restoreTenantRecycle(api: ApiClient, recycleId: string) {
  return api.post(`/recycle-bin/${encodeURIComponent(recycleId)}/restore`, {});
}

export async function getMeBoot(api: ApiClient) {
  return api.get("/me/boot");
}
'''


if __name__ == "__main__":
    main()
