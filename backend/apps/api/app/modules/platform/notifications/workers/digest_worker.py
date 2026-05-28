from __future__ import annotations

from app.modules.platform.notifications.services.digest_service import digest_service
from app.services.db import get_db_conn, set_rls_org


def run_digest_batch_for_org(org_id: str) -> dict:
    processed = 0
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, user_id::text, digest_type, payload
                FROM notifications.digest_queue
                WHERE org_id = %s::uuid AND processed = FALSE AND scheduled_for <= CURRENT_DATE
                LIMIT 200
                """,
                (org_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    by_user: dict[str, list] = {}
    for row in rows:
        by_user.setdefault(row["user_id"], []).append(row)
    for user_id, items in by_user.items():
        approval_items = [str(i.get("payload", {})) for i in items if i["digest_type"] == "approval_digest"]
        if approval_items:
            digest_service.send_approval_digest(org_id, user_id, approval_items)
            processed += 1
        risk_items = [str(i.get("payload", {})) for i in items if i["digest_type"] == "risk_digest"]
        if risk_items:
            digest_service.send_digest(org_id, user_id, "risk_digest", risk_items)
            processed += 1
        compliance_items = [str(i.get("payload", {})) for i in items if i["digest_type"] == "compliance_digest"]
        if compliance_items:
            digest_service.send_digest(org_id, user_id, "compliance_digest", compliance_items)
            processed += 1
        daily = [str(i.get("payload", {})) for i in items if i["digest_type"] == "daily_finance_summary"]
        if daily:
            digest_service.send_digest(org_id, user_id, "daily_finance_summary", daily)
            processed += 1
    if rows:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                ids = [r["id"] for r in rows]
                for did in ids:
                    cur.execute(
                        "UPDATE notifications.digest_queue SET processed = TRUE WHERE id = %s::uuid",
                        (did,),
                    )
    return {"processed_batches": processed, "rows": len(rows)}
