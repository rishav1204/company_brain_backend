from collections import Counter

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.core.config import settings


def _validated_neo4j_uri() -> str:
    uri = settings.neo4j_uri.strip()
    if settings.neo4j_require_tls:
        allowed = ("bolt+s://", "bolt+ssc://", "neo4j+s://", "neo4j+ssc://")
        if not uri.lower().startswith(allowed):
            raise RuntimeError("NEO4J_REQUIRE_TLS=true requires bolt+s:// or neo4j+s:// URI scheme")
    return uri


def _postgres_close_root_cause_rows(org_id: str, limit: int) -> list[dict]:
    from app.services.repositories import graph_data_repo

    rows: list[dict] = []
    for workflow in graph_data_repo.list_workflows_with_owner(org_id=org_id):
        if workflow.get("workflow_type") != "close":
            continue
        if workflow.get("state") not in {"blocked", "pending_approval"}:
            continue
        rows.append(
            {
                "workflow_id": workflow["workflow_id"],
                "workflow_state": workflow["state"],
                "incident_id": "intercompany-mismatch",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _postgres_ap_pattern_rows(org_id: str, limit: int) -> list[dict]:
    from app.services.repositories import graph_data_repo

    counts: Counter[str] = Counter()
    for invoice in graph_data_repo.list_invoices_with_vendor(org_id=org_id):
        vendor_id = str(invoice.get("vendor_id") or "unknown")
        counts[vendor_id] += 1
    return [{"vendor_id": vendor_id, "exception_count": count} for vendor_id, count in counts.most_common(limit)]


class Neo4jService:
    ALLOWED_LABELS = {
        "Company",
        "Department",
        "User",
        "Team",
        "Vendor",
        "Customer",
        "Invoice",
        "Payment",
        "PurchaseOrder",
        "Contract",
        "Workflow",
        "Task",
        "MemoryRecord",
        "Decision",
        "Incident",
        "Policy",
        "KPI",
    }

    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(
            _validated_neo4j_uri(),
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def _tenant_constraint_queries(self) -> list[str]:
        queries = ["DROP CONSTRAINT company_id_unique IF EXISTS"]
        for label in sorted(self.ALLOWED_LABELS):
            constraint_name = f"{label.lower()}_org_id_unique"
            queries.append(
                f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE (n.org_id, n.id) IS UNIQUE"
            )
            queries.append(f"CREATE INDEX {label.lower()}_org_idx IF NOT EXISTS FOR (n:{label}) ON (n.org_id)")
        queries.extend(
            [
                "CREATE INDEX vendor_risk_idx IF NOT EXISTS FOR (n:Vendor) ON (n.risk)",
                "CREATE INDEX workflow_type_idx IF NOT EXISTS FOR (n:Workflow) ON (n.workflow_type)",
                "CREATE INDEX workflow_state_idx IF NOT EXISTS FOR (n:Workflow) ON (n.state)",
            ]
        )
        return queries

    def upsert_node(self, label: str, node_id: str, properties: dict) -> dict:
        if label not in self.ALLOWED_LABELS:
            return {"status": "error", "detail": f"Label not allowed: {label}"}
        org_id = str(properties.get("org_id", "")).strip()
        if not org_id:
            return {"status": "error", "detail": "org_id is required for tenant-safe graph operations"}
        query = f"""
        MERGE (n:{label} {{id: $id, org_id: $org_id}})
        SET n += $properties
        RETURN n.id AS id
        """
        try:
            with self.driver.session() as session:
                record = session.run(query, id=node_id, org_id=org_id, properties=properties).single()
            return {"status": "upserted", "id": record["id"] if record else node_id}
        except Neo4jError as exc:
            return {"status": "error", "detail": str(exc)}

    def query_related(self, org_id: str, subject_id: str) -> list[str]:
        query = """
        MATCH (n {id: $id, org_id: $org_id})-[r]-(m)
        WHERE m.org_id = $org_id
        RETURN labels(n)[0] AS from_label, type(r) AS rel_type, labels(m)[0] AS to_label, m.id AS to_id
        LIMIT 25
        """
        try:
            with self.driver.session() as session:
                records = session.run(query, id=subject_id, org_id=org_id)
                return [
                    f"{record['from_label']}:{subject_id} -> {record['rel_type']} -> {record['to_label']}:{record['to_id']}"
                    for record in records
                ]
        except (Neo4jError, ServiceUnavailable, OSError):
            return []

    def bootstrap_schema(self) -> dict:
        queries = self._tenant_constraint_queries()
        executed = 0
        try:
            with self.driver.session() as session:
                for query in queries:
                    session.run(query)
                    executed += 1
            return {"status": "bootstrapped", "queries_executed": executed, "labels_constrained": len(self.ALLOWED_LABELS)}
        except Neo4jError as exc:
            return {"status": "error", "detail": str(exc), "queries_executed": executed}

    def upsert_relationship(
        self, org_id: str, from_label: str, from_id: str, rel_type: str, to_label: str, to_id: str
    ) -> dict:
        if from_label not in self.ALLOWED_LABELS or to_label not in self.ALLOWED_LABELS:
            return {"status": "error", "detail": "Label not allowed"}
        allowed_rel_types = {
            "OWNS",
            "PART_OF",
            "APPROVES",
            "BLOCKED_BY",
            "CAUSED_BY",
            "IMPACTS",
            "REFERENCES",
            "VIOLATES",
            "RELATED_TO",
            "RELATES_TO",
            "PRECEDES",
            "ISSUED",
            "PAID_BY",
            "REQUIRES_APPROVAL",
            "ASSIGNED_TO",
            "GOVERNS",
        }
        if rel_type not in allowed_rel_types:
            return {"status": "error", "detail": f"Relationship type not allowed: {rel_type}"}
        query = f"""
        MERGE (a:{from_label} {{id: $from_id, org_id: $org_id}})
        MERGE (b:{to_label} {{id: $to_id, org_id: $org_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        RETURN a.id AS from_id, b.id AS to_id
        """
        try:
            with self.driver.session() as session:
                record = session.run(query, from_id=from_id, to_id=to_id, org_id=org_id).single()
            if not record:
                return {"status": "error", "detail": "No relationship created"}
            return {"status": "upserted", "from_id": record["from_id"], "to_id": record["to_id"], "rel_type": rel_type}
        except Neo4jError as exc:
            return {"status": "error", "detail": str(exc)}

    def query_root_cause_close_delays(self, org_id: str, limit: int = 20) -> list[dict]:
        query = """
        MATCH (w:Workflow)-[:BLOCKED_BY]->(i:Incident)
        WHERE w.workflow_type = 'close' AND w.org_id = $org_id AND i.org_id = $org_id
        RETURN w.id AS workflow_id, w.state AS workflow_state, i.id AS incident_id
        LIMIT $limit
        """
        try:
            with self.driver.session() as session:
                rows = session.run(query, org_id=org_id, limit=max(1, min(limit, 100)))
                return [dict(row) for row in rows]
        except (Neo4jError, ServiceUnavailable, OSError):
            return _postgres_close_root_cause_rows(org_id=org_id, limit=max(1, min(limit, 100)))

    def query_ap_exception_patterns(self, org_id: str, limit: int = 20) -> list[dict]:
        query = """
        MATCH (v:Vendor)-[:ISSUED]->(inv:Invoice)-[:REQUIRES_APPROVAL]->(w:Workflow)
        WHERE v.org_id = $org_id AND inv.org_id = $org_id AND w.org_id = $org_id
        RETURN v.id AS vendor_id, count(inv) AS exception_count
        ORDER BY exception_count DESC
        LIMIT $limit
        """
        try:
            with self.driver.session() as session:
                rows = session.run(query, org_id=org_id, limit=max(1, min(limit, 100)))
                return [dict(row) for row in rows]
        except (Neo4jError, ServiceUnavailable, OSError):
            return _postgres_ap_pattern_rows(org_id=org_id, limit=max(1, min(limit, 100)))

    def query_decision_impact_paths(self, org_id: str, limit: int = 20) -> list[dict]:
        query = """
        MATCH (d:Decision)-[:IMPACTS]->(k:KPI)
        WHERE d.org_id = $org_id AND k.org_id = $org_id
        RETURN d.id AS decision_id, k.id AS kpi_id
        LIMIT $limit
        """
        try:
            with self.driver.session() as session:
                rows = session.run(query, org_id=org_id, limit=max(1, min(limit, 100)))
                return [dict(row) for row in rows]
        except (Neo4jError, ServiceUnavailable, OSError):
            return []


neo4j_service = Neo4jService()
