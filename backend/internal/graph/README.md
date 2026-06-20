# Graph Module

Neo4j operational graph for Finance OS relationship intelligence (M28).

## Labels (tenant-scoped via org_id)

Company, Department, User, Team, Vendor, Customer, Invoice, Payment, PurchaseOrder, Contract, Workflow, Task, MemoryRecord, Decision, Incident, Policy, KPI, Journal, GSTReturn, Reconciliation, BankTransaction, Compliance, Asset

## Relationships

OWNS, PART_OF, APPROVES, BLOCKED_BY (Workflow→Incident), CAUSED_BY, IMPACTS, REFERENCES, VIOLATES, RELATED_TO, RELATES_TO, PRECEDES, ISSUED, PAID_BY, REQUIRES_APPROVAL, ASSIGNED_TO, GOVERNS, GENERATED, SETTLED_BY, REPORTED_IN, MATCHED_IN, FILED_AS, CAPITALIZED_AS

## Services

- Platform: `neo4j_service`, `graph_service`, `graph_extraction_service`
- Finance OS: `modules/finance_os/graph/` — ingestion pipeline, lineage/dependency/causality engines, `/finance-os/graph` APIs

Used by retrieval orchestration, root-cause analysis, and M29 copilot (future).
