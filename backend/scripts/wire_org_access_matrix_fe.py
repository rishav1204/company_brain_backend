"""Append org access-matrix API helpers to platform-operator client + rewrite org controls page."""
from __future__ import annotations

from pathlib import Path

FE = Path(r"D:\new-project-fe\apps\web\src")

API_APPEND = r'''

export async function getOrgAccessMatrix(api: ApiClient, orgId: string) {
  return operatorGet<{
    org_id?: string;
    plan_key?: string;
    org_controls?: Record<string, unknown>;
    features?: Array<Record<string, unknown>>;
    screens?: Array<Record<string, unknown>>;
  }>(api, `/ops/platform/orgs/${encodeURIComponent(orgId)}/access-matrix`);
}

export async function setOrgFeature(
  api: ApiClient,
  orgId: string,
  featureCode: string,
  body: { enabled: boolean; break_glass?: boolean },
) {
  return operatorPut(
    api,
    `/ops/platform/orgs/${encodeURIComponent(orgId)}/features/${encodeURIComponent(featureCode)}`,
    body,
  );
}

export async function setOrgDeniedScreens(
  api: ApiClient,
  orgId: string,
  denied_screen_keys: string[],
) {
  return operatorPut(api, `/ops/platform/orgs/${encodeURIComponent(orgId)}/screens/denied`, {
    denied_screen_keys,
  });
}
'''

ORG_CONTROLS_PAGE = r'''"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Input,
  Label,
  LoadingSkeleton,
  PageHeader,
  Select,
} from "@finance-os/ui";
import { PlatformGoldenRuleBanner } from "@/components/platform-operator/PlatformShell";
import { useApi } from "@/hooks/use-api";
import {
  useOrgAccessMatrix,
  useOrgControls,
  usePatchOrgControls,
  useSetOrgDeniedScreens,
  useSetOrgFeature,
} from "@/hooks/use-platform-operator";
import { mapPlatformOperatorErrorToUserMessage } from "@/lib/platform-operator";

export default function OrgControlsPage() {
  const params = useParams();
  const orgId = String(params.orgId ?? "");
  const query = useOrgControls(orgId);
  const matrixQuery = useOrgAccessMatrix(orgId);
  const patch = usePatchOrgControls();
  const setFeature = useSetOrgFeature();
  const setDeniedScreens = useSetOrgDeniedScreens();
  const { api: _api } = useApi();

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
  const [msg, setMsg] = useState<string | null>(null);
  const [denied, setDenied] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");

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

  useEffect(() => {
    const keys = (matrixQuery.data?.org_controls?.denied_screen_keys as string[] | undefined) ?? [];
    const fromScreens =
      (matrixQuery.data?.screens ?? [])
        .filter((s) => s.denied === true)
        .map((s) => String(s.screen_key ?? ""))
        .filter(Boolean) ?? [];
    setDenied(new Set(keys.length ? keys.map(String) : fromScreens));
  }, [matrixQuery.data]);

  const features = useMemo(() => {
    const items = (matrixQuery.data?.features ?? []) as Array<Record<string, unknown>>;
    const q = filter.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (f) =>
        String(f.feature_code ?? "")
          .toLowerCase()
          .includes(q) ||
        String(f.name ?? "")
          .toLowerCase()
          .includes(q),
    );
  }, [matrixQuery.data, filter]);

  const screens = useMemo(() => {
    const items = (matrixQuery.data?.screens ?? []).filter(
      (s) => String(s.console ?? "erp") !== "platform",
    ) as Array<Record<string, unknown>>;
    const q = filter.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (s) =>
        String(s.screen_key ?? "")
          .toLowerCase()
          .includes(q) ||
        String(s.route_path ?? "")
          .toLowerCase()
          .includes(q) ||
        String(s.label ?? "")
          .toLowerCase()
          .includes(q),
    );
  }, [matrixQuery.data, filter]);

  if (query.isLoading || matrixQuery.isLoading) return <LoadingSkeleton rows={10} />;

  async function saveControls(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setMsg(null);
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
      setMsg("Org emergency controls saved.");
      await matrixQuery.refetch();
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    }
  }

  async function toggleFeature(code: string, enabled: boolean, onPlan: boolean) {
    setErr(null);
    setMsg(null);
    try {
      await setFeature.mutateAsync({
        orgId,
        featureCode: code,
        enabled,
        break_glass: enabled && !onPlan,
      });
      setMsg(
        enabled
          ? `Enabled ${code}${!onPlan ? " (break-glass — not on plan)" : ""}.`
          : `Disabled ${code} for this org.`,
      );
      await matrixQuery.refetch();
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
    }
  }

  async function toggleScreen(screenKey: string, deny: boolean) {
    setErr(null);
    setMsg(null);
    const next = new Set(denied);
    if (deny) next.add(screenKey);
    else next.delete(screenKey);
    setDenied(next);
    try {
      await setDeniedScreens.mutateAsync({
        orgId,
        denied_screen_keys: Array.from(next),
      });
      setMsg(deny ? `Blocked screen ${screenKey}` : `Allowed screen ${screenKey}`);
      await matrixQuery.refetch();
    } catch (error) {
      setErr(
        mapPlatformOperatorErrorToUserMessage((error as { status?: number }).status ?? 500, error),
      );
      await matrixQuery.refetch();
    }
  }

  const planKey = matrixQuery.data?.plan_key ?? "—";
  const listErr = matrixQuery.error
    ? mapPlatformOperatorErrorToUserMessage(
        (matrixQuery.error as { status?: number }).status ?? 500,
        matrixQuery.error,
      )
    : null;

  return (
    <div>
      <PageHeader
        title="Org access matrix"
        description="Emergency org switches + per-feature entitlements + per-screen blocks"
      />
      <PlatformGoldenRuleBanner />
      <p className="mb-3 text-sm text-muted-foreground">
        Org <code className="text-xs">{orgId}</code> · plan <code className="text-xs">{planKey}</code>
      </p>
      {listErr || err ? <p className="mb-3 text-sm text-destructive">{listErr ?? err}</p> : null}
      {msg ? <p className="mb-3 text-sm text-emerald-600 dark:text-emerald-400">{msg}</p> : null}

      <div className="mb-4">
        <Input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter features / screens…"
        />
      </div>

      <form className="mb-8 max-w-xl space-y-3 rounded-md border p-4" onSubmit={(e) => void saveControls(e)}>
        <h2 className="text-sm font-medium">Emergency org controls</h2>
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
            ["ai_enabled", "AI master (all AI features)"],
            ["erp_modules_enabled", "ERP modules master"],
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
        <Button type="submit" disabled={patch.isPending}>
          {patch.isPending ? "Saving…" : "Save emergency controls"}
        </Button>
      </form>

      <section className="mb-10">
        <h2 className="mb-1 text-sm font-medium">Features (per org)</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Toggle uses billing entitlement overrides. Turning off blocks APIs and nav gated by that
          feature. Enabling a feature not on the org plan uses audited break-glass.
        </p>
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b bg-muted/40">
              <tr>
                <th className="px-3 py-2 font-medium">Feature</th>
                <th className="px-3 py-2 font-medium">Plan</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">Effective</th>
                <th className="px-3 py-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {features.map((f) => {
                const code = String(f.feature_code ?? "");
                const enabled = f.enabled === true;
                const onPlan = f.on_plan === true;
                return (
                  <tr key={code} className="border-b last:border-0">
                    <td className="px-3 py-2">
                      <div className="font-medium">{String(f.name ?? code)}</div>
                      <code className="text-xs text-muted-foreground">{code}</code>
                      {f.is_ai ? (
                        <span className="ml-2 text-xs text-muted-foreground">AI</span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">{onPlan ? "on plan" : "not on plan"}</td>
                    <td className="px-3 py-2">
                      <code className="text-xs">{String(f.source ?? "—")}</code>
                    </td>
                    <td className="px-3 py-2">{enabled ? "allowed" : "blocked"}</td>
                    <td className="px-3 py-2">
                      <Button
                        variant="outline"
                        disabled={setFeature.isPending}
                        onClick={() => void toggleFeature(code, !enabled, onPlan)}
                      >
                        {enabled ? "Disable" : "Enable"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
              {features.length === 0 ? (
                <tr>
                  <td className="px-3 py-4 text-muted-foreground" colSpan={5}>
                    No features (restart API if access-matrix route is missing).
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-1 text-sm font-medium">Screens (per org denylist)</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Blocked screens are hidden from nav once FE/boot enforces them and still blocked in boot
          resolution. Screens without a feature stay independent of entitlement toggles.
        </p>
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b bg-muted/40">
              <tr>
                <th className="px-3 py-2 font-medium">Screen</th>
                <th className="px-3 py-2 font-medium">Route</th>
                <th className="px-3 py-2 font-medium">Feature</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {screens.map((s) => {
                const key = String(s.screen_key ?? "");
                const isDenied = denied.has(key) || s.denied === true;
                const allowed = s.allowed === true && !isDenied;
                return (
                  <tr key={key} className="border-b last:border-0">
                    <td className="px-3 py-2">
                      <div className="font-medium">{String(s.label ?? key)}</div>
                      <code className="text-xs text-muted-foreground">{key}</code>
                    </td>
                    <td className="px-3 py-2">
                      <code className="text-xs">{String(s.route_path ?? "—")}</code>
                    </td>
                    <td className="px-3 py-2">{String(s.feature_code ?? "—")}</td>
                    <td className="px-3 py-2">{allowed ? "allowed" : "blocked"}</td>
                    <td className="px-3 py-2">
                      <Button
                        variant="outline"
                        disabled={setDeniedScreens.isPending}
                        onClick={() => void toggleScreen(key, !isDenied)}
                      >
                        {isDenied ? "Allow" : "Block"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
              {screens.length === 0 ? (
                <tr>
                  <td className="px-3 py-4 text-muted-foreground" colSpan={5}>
                    No screens loaded.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
'''


def main() -> None:
    api = FE / "lib" / "platform-operator" / "api.ts"
    at = api.read_text(encoding="utf-8")
    if "getOrgAccessMatrix" not in at:
        api.write_text(at + API_APPEND, encoding="utf-8")
        print("api helpers appended")
    else:
        print("api already has access matrix")

    hooks = FE / "hooks" / "use-platform-operator.ts"
    ht = hooks.read_text(encoding="utf-8")
    if "getOrgAccessMatrix" not in ht:
        ht = ht.replace(
            "listPlatformScreens,",
            "listPlatformScreens,\n  getOrgAccessMatrix,\n  setOrgFeature,\n  setOrgDeniedScreens,",
        )
    if "useOrgAccessMatrix" not in ht:
        ht += r'''

export function useOrgAccessMatrix(orgId: string, enabled = true) {
  const { api, isReady } = useApi();
  return useQuery({
    queryKey: ["platform-operator", "access-matrix", orgId],
    enabled: isReady && enabled && !!orgId,
    queryFn: () => getOrgAccessMatrix(api, orgId),
  });
}

export function useSetOrgFeature() {
  const { api } = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      orgId: string;
      featureCode: string;
      enabled: boolean;
      break_glass?: boolean;
    }) =>
      setOrgFeature(api, input.orgId, input.featureCode, {
        enabled: input.enabled,
        break_glass: input.break_glass,
      }),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["platform-operator", "access-matrix", vars.orgId] });
    },
  });
}

export function useSetOrgDeniedScreens() {
  const { api } = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { orgId: string; denied_screen_keys: string[] }) =>
      setOrgDeniedScreens(api, input.orgId, input.denied_screen_keys),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["platform-operator", "access-matrix", vars.orgId] });
      qc.invalidateQueries({ queryKey: ["platform-operator", "org-controls", vars.orgId] });
    },
  });
}
'''
    hooks.write_text(ht, encoding="utf-8")
    print("hooks updated")

    page = (
        FE
        / "app"
        / "(platform)"
        / "platform"
        / "orgs"
        / "[orgId]"
        / "controls"
        / "page.tsx"
    )
    page.write_text(ORG_CONTROLS_PAGE, encoding="utf-8")
    print("org controls page written")

    # Update catalog Features page helper text for org matrix
    feat = FE / "app" / "(platform)" / "platform" / "features" / "page.tsx"
    ft = feat.read_text(encoding="utf-8")
    old = "Freeze login, kill AI, or disable ERP modules per tenant without redeploying."
    new = "Open Configure on an org for feature toggles, screen blocks, and emergency kills."
    if old in ft:
        ft = ft.replace(old, new)
        feat.write_text(ft, encoding="utf-8")
        print("features page copy updated")


if __name__ == "__main__":
    main()
