"""Apply erp.coa_versions snapshots to period-close reporting output (ERP-01)."""

from __future__ import annotations


def _account_lookups(snapshot: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    accounts = snapshot.get("accounts") or []
    by_id: dict[str, dict] = {}
    by_code: dict[str, dict] = {}
    for account in accounts:
        if not isinstance(account, dict):
            continue
        aid = str(account.get("id") or "").strip()
        code = str(account.get("account_code") or account.get("code") or "").strip()
        if aid:
            by_id[aid] = account
        if code:
            by_code[code] = account
    return by_id, by_code


def _resolve_snapshot_account(line: dict, by_id: dict[str, dict], by_code: dict[str, dict]) -> dict | None:
    aid = str(line.get("account_id") or "").strip()
    code = str(line.get("account_code") or line.get("code") or "").strip()
    return by_id.get(aid) or by_code.get(code)


def apply_snapshot_to_lines(lines: list[dict], snapshot: dict) -> list[dict]:
    by_id, by_code = _account_lookups(snapshot)
    out: list[dict] = []
    for line in lines:
        row = dict(line)
        snap = _resolve_snapshot_account(row, by_id, by_code)
        if snap:
            row["account_name"] = snap.get("account_name") or snap.get("name") or row.get("account_name")
            row["account_code"] = snap.get("account_code") or snap.get("code") or row.get("account_code")
            row["account_type"] = snap.get("account_type") or snap.get("type") or row.get("account_type")
            row["reporting_category"] = (
                snap.get("reporting_category")
                or snap.get("account_type")
                or row.get("reporting_category")
            )
            row["coa_snapshot_applied"] = True
        else:
            row["coa_snapshot_applied"] = False
        out.append(row)
    return out


def apply_snapshot_to_sections(sections: list[dict], snapshot: dict) -> list[dict]:
    return apply_snapshot_to_lines(sections, snapshot)


def snapshot_meta(snapshot: dict) -> dict:
    accounts = snapshot.get("accounts") or []
    return {
        "coa_version_applied": True,
        "coa_accounts_snapshot_count": len(accounts),
        "coa_groups_snapshot_count": len(snapshot.get("groups") or []),
    }
