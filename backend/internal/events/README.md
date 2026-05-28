# Events Module

Queue stack:
- Redis + BullMQ (MVP)

Core queues:
- `ingestion.sync`, `ingestion.retry`
- `processing.chunk`, `processing.embed`, `processing.extract`
- `graph.upsert`, `memory.write`, `retrieval.precompute`
- `agent.run`, `agent.action`
- `notifications.dispatch`, `audit.persist`

All events use standard envelope fields:
`event_id`, `event_type`, `org_id`, `source`, `occurred_at`, `trace_id`, `payload`, `schema_version`
