#!/usr/bin/env python3
"""Architecture review audit — scans codebase and reports structural risks."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "apps" / "api" / "app"
MIGRATIONS = REPO / "migrations"
OUT = REPO / "ENTERPRISE_ARCHITECTURE_REVIEW_DATA.json"

SCHEMA_REPO_SUFFIXES = (
    "schema_repository.py",
)

# Known remediated patterns (audit should not flag when fixed)
REMEDIATED_CHECKS = {
    "gl_direct_post_bypass": APP / "modules" / "erp" / "gl" / "routes" / "posting_routes.py",
    "db_connection_pool": APP / "services" / "db.py",
    "redis_stream_maxlen": APP / "modules" / "platform" / "events" / "queues" / "queue_manager.py",
    "redis_legacy_dedup_ttl": APP / "services" / "redis_queue_service.py",
    "migration_066_indexes": MIGRATIONS / "066_architecture_review_indexes.sql",
    "migration_readiness": APP / "services" / "migration_readiness.py",
}


def module_key(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if parts[0] == "modules" and len(parts) >= 3:
        return "/".join(parts[:3])
    if parts[0] == "services":
        return "legacy/services"
    if parts[0] == "api":
        return "legacy/api"
    return parts[0]


def _is_schema_repo(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    return norm.endswith(SCHEMA_REPO_SUFFIXES) or "information_schema" in Path(APP / rel).read_text(
        encoding="utf-8", errors="ignore"
    ) if (APP / rel).exists() else False


def scan_imports() -> dict:
    edges: dict[str, set[str]] = defaultdict(set)
    modules: dict[str, dict] = defaultdict(
        lambda: {"services": 0, "repos": 0, "routes": 0, "events": 0, "files": 0}
    )
    cross = {
        "erp_to_fos": [],
        "fos_to_erp": [],
        "fos_to_legacy": [],
        "erp_to_legacy": [],
        "fos_posting_orchestrator": [],
    }
    no_rls_repo: list[str] = []
    unbounded_fetch: list[str] = []
    missing_limit_list: list[str] = []

    for py in APP.rglob("*.py"):
        rel = str(py.relative_to(APP))
        mk = module_key(rel)
        modules[mk]["files"] += 1
        if "/services/" in rel and rel.endswith(".py"):
            modules[mk]["services"] += 1
        if "/repositories/" in rel:
            modules[mk]["repos"] += 1
        if "/routes/" in rel:
            modules[mk]["routes"] += 1
        if "/events/" in rel and rel.endswith("_events.py"):
            modules[mk]["events"] += 1

        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for m in re.finditer(r"from (app\.(?:modules\.[a-z0-9_/]+|services\.[a-z0-9_]+))", text):
            imp = m.group(1)
            if imp.startswith("app.modules."):
                dst_parts = imp.replace("app.modules.", "").split(".")
                dst = (
                    "/".join(dst_parts[:3])
                    if dst_parts[0] in ("erp", "platform", "finance_os", "core", "workflows")
                    else dst_parts[0]
                )
            else:
                dst = "legacy/services"
            if mk != dst:
                edges[mk].add(dst)

        norm = rel.replace("\\", "/")
        if "/erp/" in norm:
            if "from app.modules.finance_os" in text:
                cross["erp_to_fos"].append(rel)
            if re.search(r"from app\.services\.", text) and "/repositories/" not in norm:
                cross["erp_to_legacy"].append(rel)
        if "/finance_os/" in norm:
            if "from app.modules.erp" in text:
                cross["fos_to_erp"].append(rel)
            if re.search(r"from app\.services\.", text):
                cross["fos_to_legacy"].append(rel)
            if "posting_orchestrator" in text:
                cross["fos_posting_orchestrator"].append(rel)

        if "/repositories/" in norm:
            if "get_db_conn" in text and "set_rls_org" not in text and not _is_schema_repo(rel):
                no_rls_repo.append(rel)
            if "fetchall()" in text:
                blocks = re.split(r"cur\.execute\(", text)
                for block in blocks[1:]:
                    snippet = block[:800]
                    if "fetchall()" in snippet and "LIMIT" not in snippet.upper():
                        if re.search(r"limit\s*=\s*max\(", text) or "params.append(limit)" in snippet:
                            continue
                        unbounded_fetch.append(f"{rel}: unbounded fetchall")
                        break
            for fn in re.finditer(r"def (list_\w+|search_\w+|get_all\w*)\([^)]*\)", text):
                fn_name = fn.group(1)
                start = fn.end()
                chunk = text[start : start + 800]
                if "LIMIT" not in chunk.upper() and "fetchone" not in chunk:
                    if "limit:" in chunk or "limit =" in chunk:
                        continue
                    missing_limit_list.append(f"{rel}:{fn_name}")

    return {
        "module_counts": {k: dict(v) for k, v in sorted(modules.items())},
        "import_edges": {k: sorted(v) for k, v in sorted(edges.items())},
        "cross_boundary": cross,
        "repos_missing_set_rls_org": no_rls_repo,
        "unbounded_fetchall": list(dict.fromkeys(unbounded_fetch))[:80],
        "list_methods_missing_limit": list(dict.fromkeys(missing_limit_list))[:80],
    }


def scan_remediation_status() -> dict:
    status: dict[str, bool] = {}
    gl_route = REMEDIATED_CHECKS["gl_direct_post_bypass"]
    if gl_route.exists():
        text = gl_route.read_text(encoding="utf-8", errors="ignore")
        status["gl_routes_through_journal_orchestrator"] = "posting_orchestrator" in text and "posting_service.post" not in text
    else:
        status["gl_routes_through_journal_orchestrator"] = False

    db_py = REMEDIATED_CHECKS["db_connection_pool"]
    if db_py.exists():
        text = db_py.read_text(encoding="utf-8", errors="ignore")
        status["postgres_connection_pool"] = "ConnectionPool" in text
    else:
        status["postgres_connection_pool"] = False

    qm = REMEDIATED_CHECKS["redis_stream_maxlen"]
    if qm.exists():
        text = qm.read_text(encoding="utf-8", errors="ignore")
        status["redis_stream_maxlen"] = "maxlen=" in text
    else:
        status["redis_stream_maxlen"] = False

    rq = REMEDIATED_CHECKS["redis_legacy_dedup_ttl"]
    if rq.exists():
        text = rq.read_text(encoding="utf-8", errors="ignore")
        status["redis_legacy_dedup_ttl"] = "setex" in text and "sadd" not in text
    else:
        status["redis_legacy_dedup_ttl"] = False

    status["migration_066_present"] = REMEDIATED_CHECKS["migration_066_indexes"].exists()
    status["migration_067_present"] = (MIGRATIONS / "067_p1_tenancy_hardening.sql").exists()
    status["migration_readiness_service"] = REMEDIATED_CHECKS["migration_readiness"].exists()

    legacy_guard = APP / "services" / "legacy_write_guard.py"
    status["legacy_write_guard"] = legacy_guard.exists() and "block_legacy_accounting_write" in legacy_guard.read_text(
        encoding="utf-8", errors="ignore"
    )
    org_val = APP / "services" / "event_org_validation.py"
    status["event_org_id_required"] = org_val.exists() and "require_org_id" in org_val.read_text(
        encoding="utf-8", errors="ignore"
    )
    evt_svc = APP / "modules" / "platform" / "events" / "services" / "event_service.py"
    if evt_svc.exists():
        text = evt_svc.read_text(encoding="utf-8", errors="ignore")
        status["event_publish_validates_org"] = "require_org_id" in text
    else:
        status["event_publish_validates_org"] = False
    company_scope = APP / "modules" / "erp" / "security" / "company_scope.py"
    status["erp_company_scope"] = company_scope.exists()
    handlers = APP / "services" / "event_consumers_handlers.py"
    router = APP / "services" / "event_consumers_router.py"
    status["event_consumers_split"] = handlers.exists() and router.exists()

    payment = APP / "modules" / "erp" / "accounts_payable" / "services" / "payment_service.py"
    if payment.exists():
        text = payment.read_text(encoding="utf-8", errors="ignore")
        status["ap_payment_atomic_completion"] = (
            "post_journal_with_conn" in text and "record_payment_conn" in text and "record_payment_debit_conn" in text
        )
        status["ap_bank_tx_errors_propagate"] = "record_payment_debit_conn" in text
    else:
        status["ap_payment_atomic_completion"] = False
        status["ap_bank_tx_errors_propagate"] = False

    collection = APP / "modules" / "erp" / "accounts_receivable" / "services" / "collection_service.py"
    if collection.exists():
        text = collection.read_text(encoding="utf-8", errors="ignore")
        status["ar_receipt_atomic_completion"] = (
            "post_journal_with_conn" in text and "record_receipt_conn" in text and "record_receipt_credit_conn" in text
        )
    else:
        status["ar_receipt_atomic_completion"] = False

    qm_path = REMEDIATED_CHECKS["redis_stream_maxlen"]
    if qm_path.exists():
        qm_text = qm_path.read_text(encoding="utf-8", errors="ignore")
        status["queue_delayed_retry_release"] = "lpush(queue, raw)" in qm_text
        status["redis_shared_pool"] = "redis_client" in qm_text
        status["consumer_dedup_ttl_7d"] = "CONSUMER_DEDUP_TTL_SECONDS" in qm_text
    else:
        status["queue_delayed_retry_release"] = False
        status["redis_shared_pool"] = False
        status["consumer_dedup_ttl_7d"] = False

    redis_client = APP / "services" / "redis_client.py"
    status["redis_client_module"] = redis_client.exists()

    worker = APP / "services" / "worker_service.py"
    if worker.exists():
        wtext = worker.read_text(encoding="utf-8", errors="ignore")
        status["queue_jobs_lifecycle"] = "update_job_by_event" in wtext
    else:
        status["queue_jobs_lifecycle"] = False

    status["migration_068_present"] = (MIGRATIONS / "068_p2_scalability_and_tenancy.sql").exists()

    consumers_dir = APP / "modules" / "platform" / "events" / "consumers"
    status["event_consumers_modular"] = (
        (consumers_dir / "erp_consumer.py").exists()
        and (consumers_dir / "workflow_consumer.py").exists()
        and (consumers_dir / "finance_os_consumer.py").exists()
        and (consumers_dir / "ingestion_consumer.py").exists()
    )

    fos_mem = APP / "modules" / "finance_os" / "memory" / "repositories" / "memory_store_repository.py"
    status["finance_os_memory_repo"] = fos_mem.exists()

    return status


def scan_migrations() -> dict:
    tables: dict[str, dict] = {}
    for sql in sorted(MIGRATIONS.glob("*.sql")):
        text = sql.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(
            r"CREATE TABLE(?: IF NOT EXISTS)?\s+([a-z_]+\.[a-z_]+|[a-z_]+)\s*\((.*?)\)\s*;",
            text,
            re.I | re.S,
        ):
            tname = m.group(1)
            if "." not in tname:
                tname = f"public.{tname}"
            body = m.group(2)
            tables.setdefault(
                tname,
                {
                    "first_migration": sql.name,
                    "org_id": bool(re.search(r"\borg_id\b", body)),
                    "company_id": bool(re.search(r"\bcompany_id\b", body)),
                    "rls": False,
                    "force_rls": False,
                    "indexes": [],
                    "unique_constraints": [],
                },
            )
            tables[tname]["org_id"] = tables[tname]["org_id"] or bool(re.search(r"\borg_id\b", body))
            tables[tname]["company_id"] = tables[tname]["company_id"] or bool(
                re.search(r"\bcompany_id\b", body)
            )

    for sql in sorted(MIGRATIONS.glob("*.sql")):
        text = sql.read_text(encoding="utf-8", errors="ignore")
        for tname in tables:
            schema, short = tname.split(".", 1) if "." in tname else ("public", tname)
            if re.search(rf"ALTER TABLE\s+(?:{re.escape(tname)}|{short})\s", text, re.I):
                if "ROW LEVEL SECURITY" in text:
                    tables[tname]["rls"] = True
                if "FORCE ROW LEVEL SECURITY" in text:
                    tables[tname]["force_rls"] = True
            if re.search(rf"CREATE (?:UNIQUE )?INDEX[^;]+ON\s+{re.escape(tname)}\b", text, re.I):
                tables[tname]["indexes"].append(sql.name)
            elif schema == "public" and re.search(rf"CREATE (?:UNIQUE )?INDEX[^;]+ON\s+{short}\b", text, re.I):
                tables[tname]["indexes"].append(sql.name)

    tenant_no_rls = [t for t, d in tables.items() if d["org_id"] and not d["rls"]]
    tenant_no_idx = [t for t, d in tables.items() if d["org_id"] and not d["indexes"]]
    erp_no_org = [
        t
        for t, d in tables.items()
        if t.startswith("erp.") and not d["org_id"] and "compliance_types" not in t
    ]
    schemas: dict[str, int] = defaultdict(int)
    for t in tables:
        schemas[t.split(".")[0]] += 1

    return {
        "total_tables": len(tables),
        "schemas": dict(schemas),
        "tenant_tables_no_rls": tenant_no_rls,
        "tenant_tables_no_index": tenant_no_idx[:50],
        "erp_tables_no_org_id": erp_no_org,
        "tables": tables,
    }


def scan_redis() -> dict:
    patterns: list[dict] = []
    unbounded_streams = []
    for py in APP.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "redis" not in text.lower() and "setex" not in text and "expire" not in text:
            continue
        rel = str(py.relative_to(APP))
        if "xadd" in text and "maxlen" not in text and "queue_manager" in rel:
            unbounded_streams.append(rel)
        for line_no, line in enumerate(text.splitlines(), 1):
            if not any(
                x in line
                for x in ("redis", "setex", "expire", "xadd", "rpush", "publish", "incr", "set(")
            ):
                continue
            ttl = None
            if "setex" in line or "expire" in line:
                m = re.search(r"(?:setex|expire)\([^,]+,\s*(\d+)", line)
                if m:
                    ttl = int(m.group(1))
            patterns.append({"file": rel, "line": line_no, "snippet": line.strip()[:120], "ttl": ttl})
    return {
        "redis_usages": patterns[:120],
        "total_redis_files": len({p["file"] for p in patterns}),
        "xadd_without_maxlen": unbounded_streams,
    }


def scan_queues() -> dict:
    config_path = APP / "core" / "config.py"
    text = config_path.read_text(encoding="utf-8")
    queues = re.findall(r'queue_\w+_name:\s*str\s*=\s*"([^"]+)"', text)
    topology_path = APP / "services" / "event_topology.py"
    topo = topology_path.read_text(encoding="utf-8", errors="ignore") if topology_path.exists() else ""
    groups = re.findall(r'"([^"]+)"', topo)
    return {"config_queue_names": sorted(set(queues))[:60], "topology_refs": groups[:40]}


def summarize(data: dict) -> dict:
    remediation = data.get("remediation", {})
    open_issues = []
    if not remediation.get("gl_routes_through_journal_orchestrator"):
        open_issues.append("GL direct post bypass")
    if not remediation.get("postgres_connection_pool"):
        open_issues.append("No Postgres connection pool")
    if not remediation.get("ap_payment_atomic_completion"):
        open_issues.append("AP payment completion not atomic")
    if not remediation.get("redis_stream_maxlen"):
        open_issues.append("Redis streams unbounded")
    if not remediation.get("redis_legacy_dedup_ttl"):
        open_issues.append("Legacy Redis dedup without TTL")
    if not remediation.get("migration_066_present"):
        open_issues.append("Missing migration 066 indexes")
    if not remediation.get("migration_067_present"):
        open_issues.append("Missing migration 067 tenancy hardening")
    if not remediation.get("legacy_write_guard"):
        open_issues.append("Legacy accounting write guard missing")
    if not remediation.get("event_org_id_required"):
        open_issues.append("Event org_id validation missing")
    if not remediation.get("event_publish_validates_org"):
        open_issues.append("Event publish does not require org_id")
    if not remediation.get("ar_receipt_atomic_completion"):
        open_issues.append("AR receipt completion not atomic")
    if not remediation.get("queue_delayed_retry_release"):
        open_issues.append("List-mode delayed retry stall")
    if not remediation.get("queue_jobs_lifecycle"):
        open_issues.append("queue_jobs not updated on consume")
    if not remediation.get("redis_client_module"):
        open_issues.append("Shared Redis pool missing")
    if not remediation.get("migration_068_present"):
        open_issues.append("Missing migration 068")
    if not remediation.get("event_consumers_modular"):
        open_issues.append("Event consumers not modularized")
    return {
        "open_remediation_issues": open_issues,
        "remediation_passed": len(open_issues) == 0,
        "unbounded_fetchall_count": len(data["imports"]["unbounded_fetchall"]),
        "repos_missing_rls": len(data["imports"]["repos_missing_set_rls_org"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run enterprise architecture audit")
    parser.add_argument("--fail-on-open", action="store_true", help="Exit 1 if remediation issues remain")
    args = parser.parse_args()

    data = {
        "imports": scan_imports(),
        "migrations": scan_migrations(),
        "redis": scan_redis(),
        "queues": scan_queues(),
        "remediation": scan_remediation_status(),
    }
    data["summary"] = summarize(data)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print("tables", data["migrations"]["total_tables"])
    print("tenant_no_rls", len(data["migrations"]["tenant_tables_no_rls"]))
    print("remediation", data["remediation"])
    print("summary", data["summary"])
    if args.fail_on_open and data["summary"]["open_remediation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
