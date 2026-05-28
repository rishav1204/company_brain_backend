from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.coa.repositories.account_group_repository import account_group_repository
from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.coa.repositories.cost_center_repository import cost_center_repository

router = APIRouter()


def _build_tree(nodes: list[dict], *, id_key: str = "id", parent_key: str = "parent_id") -> list[dict]:
    by_id = {n[id_key]: {**n, "children": []} for n in nodes if n.get(id_key)}
    roots: list[dict] = []
    for n in by_id.values():
        pid = n.get(parent_key)
        if pid and pid in by_id:
            by_id[pid]["children"].append(n)
        else:
            roots.append(n)
    return roots


@router.get("/coa/tree")
def coa_tree(context=Depends(build_request_context), company_id: str | None = Query(default=None)) -> dict:
    groups = account_group_repository.list(context.org_id, company_id=company_id, limit=1000)
    accounts = account_repository.list(context.org_id, company_id=company_id, limit=2000)
    cost_centers = cost_center_repository.list(context.org_id, company_id=company_id, limit=2000)

    groups_nodes = [
        {
            "id": g["id"],
            "code": g.get("group_code"),
            "name": g.get("group_name"),
            "group_type": g.get("group_type"),
            "nature": g.get("nature"),
            "parent_id": g.get("parent_group_id"),
        }
        for g in groups
    ]
    accounts_nodes = [
        {
            "id": a["id"],
            "code": a.get("account_code"),
            "name": a.get("account_name"),
            "account_type": a.get("account_type"),
            "group_id": a.get("group_id"),
            "parent_id": a.get("parent_account_id"),
            "is_postable": a.get("is_postable"),
            "is_active": a.get("is_active"),
        }
        for a in accounts
    ]
    cost_center_nodes = [
        {
            "id": c["id"],
            "code": c.get("cost_center_code"),
            "name": c.get("cost_center_name"),
            "parent_id": c.get("parent_cost_center_id"),
            "is_active": c.get("is_active"),
        }
        for c in cost_centers
    ]

    return {
        "request_id": context.request_id,
        "item": {
            "groups_tree": _build_tree(groups_nodes, id_key="id", parent_key="parent_id"),
            "accounts_tree": _build_tree(accounts_nodes, id_key="id", parent_key="parent_id"),
            "cost_centers_tree": _build_tree(cost_center_nodes, id_key="id", parent_key="parent_id"),
        },
    }


@router.get("/accounts/search")
def search_accounts(
    context=Depends(build_request_context),
    q: str = Query(..., min_length=1, max_length=256),
    company_id: str | None = Query(default=None),
) -> dict:
    qn = q.strip().lower()
    items = account_repository.list(context.org_id, company_id=company_id, limit=2000)
    matches = [
        a
        for a in items
        if qn in str(a.get("account_code") or "").lower() or qn in str(a.get("account_name") or "").lower()
    ][:100]
    return {"request_id": context.request_id, "items": matches}

