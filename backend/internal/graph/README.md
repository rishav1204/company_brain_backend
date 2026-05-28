# Graph Module

This module maps canonical entities into Neo4j.

Initial labels:
- `Person`, `Team`, `Vendor`, `Customer`, `Contract`, `Invoice`, `Workflow`,
  `WorkflowStep`, `Decision`, `Incident`, `Policy`, `KPI`

Initial relationships:
- `OWNS`, `PART_OF`, `APPROVES`, `BLOCKED_BY`, `CAUSED_BY`, `IMPACTS`,
  `REFERENCES`, `VIOLATES`, `RELATED_TO`, `PRECEDES`

This service is used by retrieval orchestration and root-cause analysis APIs.
