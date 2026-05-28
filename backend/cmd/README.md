# Command Entrypoints

Suggested binaries:
- `api-server`
- `connector-worker`
- `knowledge-worker`
- `agent-runner`
- `audit-worker`

Implemented local worker entrypoints:
- `worker.py` -> runs queue worker loop (`run_queue_worker_once`)
- `scheduler.py` -> runs scheduler loop (`run_scheduled_jobs_once`)

Ops API parity:
- `/api/v1/ops/worker/run-batch` invokes bounded worker batch iterations for queue topology validation.
