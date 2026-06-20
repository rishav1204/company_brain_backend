"""Backfill Finance OS memory from historical sources."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.modules.finance_os.memory.services.memory_writer_service import memory_writer_service
from app.services.db import get_db_conn, set_rls_org
from app.services.repositories import memory_repo


def _backfill_legacy(org_id: str) -> int:
    count = 0
    for row in memory_repo.list_memory(org_id=org_id):
        payload = row.get("payload_jsonb") or {}
        if payload.get("finance_os_memory_id"):
            continue
        content = payload.get("content") or str(payload)
        title = payload.get("title") or f"Legacy {row.get('memory_type')}"
        result = memory_writer_service.write(
            org_id,
            memory_type=str(row.get("memory_type", "user")),
            entity_type=None,
            entity_id=None,
            title=title,
            content=content,
            importance_score=float(row.get("relevance_score", 0.6)) * 100,
            source_event_type="backfill.legacy",
            force=True,
        )
        if result:
            count += 1
    return count


def _backfill_workflow_patterns(org_id: str) -> int:
    count = 0
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT workflow_type, step_key, p95_seconds::float8 AS p95
                    FROM finance_os.workflow_stage_metrics
                    WHERE org_id = %s::uuid
                    ORDER BY p95_seconds DESC
                    LIMIT 50
                    """,
                    (org_id,),
                )
                rows = [dict(r) for r in cur.fetchall()]
            except Exception:
                return 0
    for row in rows:
        wf = row.get("workflow_type", "workflow")
        step = row.get("step_key", "stage")
        p95 = row.get("p95", 0)
        result = memory_writer_service.write(
            org_id,
            memory_type="approval",
            entity_type="workflow_type",
            entity_id=None,
            title=f"{wf} stage latency",
            content=f"Stage {step} p95 latency {p95:.0f}s for {wf}",
            importance_score=68.0,
            source_event_type="backfill.workflow_metrics",
            metadata={"workflow_type": wf, "step_key": step},
            force=True,
        )
        if result:
            count += 1
    return count


def backfill_org(org_id: str) -> dict:
    legacy = _backfill_legacy(org_id)
    workflow = _backfill_workflow_patterns(org_id)
    return {"legacy_migrated": legacy, "workflow_patterns": workflow, "org_id": org_id}


if __name__ == "__main__":
    import os

    target = os.environ.get("ORG_ID", "")
    if not target:
        print("Set ORG_ID env var")
        sys.exit(1)
    print(backfill_org(target))
