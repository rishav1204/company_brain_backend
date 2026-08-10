"""Fix FE control-plane API helpers and support page location."""
from __future__ import annotations

from pathlib import Path
import shutil

FE = Path(r"D:\new-project-fe\apps\web\src")

CONTROL_BLOCK = r'''
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
  return operatorPatch(
    api,
    `${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}`,
    body,
  );
}

export async function replaceAdminPlanFeatures(
  api: ApiClient,
  planKey: string,
  features: Array<string | { feature_code: string; enabled?: boolean }>,
) {
  return operatorPut(
    api,
    `${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}/features`,
    { features },
  );
}

export async function replaceAdminPlanLimits(
  api: ApiClient,
  planKey: string,
  limits: Array<{ limit_code: string; limit_value: number }>,
) {
  return operatorPut(
    api,
    `${ADMIN_BILLING_PREFIX}/plans/${encodeURIComponent(planKey)}/limits`,
    { limits },
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
  return operatorPatch(api, `/ops/platform/orgs/${encodeURIComponent(orgId)}/controls`, body);
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


def main() -> None:
    paths = FE / "lib" / "platform-operator" / "paths.ts"
    t = paths.read_text(encoding="utf-8")
    if "operatorPatch" not in t:
        t += """

export function operatorPatch<T>(api: ApiClient, path: string, body?: unknown) {
  return api.patch<T>(path, body ?? {});
}

export function operatorPut<T>(api: ApiClient, path: string, body?: unknown) {
  return api.put<T>(path, body ?? {});
}
"""
        paths.write_text(t, encoding="utf-8")
        print("paths ok")

    api = FE / "lib" / "platform-operator" / "api.ts"
    at = api.read_text(encoding="utf-8")
    if "operatorPatch" not in at.split("from \"./paths\"")[0]:
        at = at.replace(
            """  operatorGet,
  operatorPost,
  OPS_PLATFORM_PREFIX,
} from \"./paths\";""",
            """  operatorGet,
  operatorPost,
  operatorPatch,
  operatorPut,
  OPS_PLATFORM_PREFIX,
} from \"./paths\";""",
        )
    start = at.find("/* ── Control plane")
    if start > 0:
        at = at[:start] + CONTROL_BLOCK
    api.write_text(at, encoding="utf-8")
    print("api ok")

    cp = FE / "lib" / "control-plane" / "api.ts"
    ct = cp.read_text(encoding="utf-8")
    ct = ct.replace(
        'import type { ApiClient } from "@/lib/api-client";',
        'import type { ApiClient } from "@finance-os/api-client";',
    )
    cp.write_text(ct, encoding="utf-8")

    # Support page under (workspace)
    src = FE / "app" / "(app)" / "support" / "page.tsx"
    dest = FE / "app" / "(workspace)" / "support" / "page.tsx"
    if src.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        # cleanup empty dirs
        try:
            src.parent.rmdir()
            src.parent.parent.rmdir()
        except OSError:
            pass
        print("moved support to workspace")
    elif dest.exists():
        print("support already in workspace")
    else:
        print("WARNING: support page missing")

    # Admin activity/recycle already under admin - good

    # Link orgs page lightly if simple
    orgs = FE / "app" / "(platform)" / "platform" / "orgs" / "page.tsx"
    if orgs.exists():
        ot = orgs.read_text(encoding="utf-8")
        if "controls" not in ot:
            print("orgs page has no controls link (optional)")

    # verify Button size usage - strip size props if needed later via tsc
    for path in (FE / "app").rglob("page.tsx"):
        text = path.read_text(encoding="utf-8")
        if 'size="sm"' in text and "platform" in str(path).replace("\\", "/"):
            text2 = text.replace(' size="sm"', "")
            if text2 != text:
                path.write_text(text2, encoding="utf-8")
                print("stripped size sm", path)

    # billing plan type include monthly_ai_credits already
    print("done")


if __name__ == "__main__":
    main()
