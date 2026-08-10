# Command Entrypoints

Suggested binaries:
- `api-server`
- `connector-worker`
- `knowledge-worker`
- `agent-runner`
- `audit-worker`

Implemented local worker entrypoints:
- `worker.py` -> runs queue worker loop (`run_queue_worker_batch`)
- `scheduler.py` -> runs scheduler loop (`run_scheduled_jobs_once`)

Local run (from repo root or `backend/`):

```powershell
$env:PYTHONPATH = "D:\new_project\backend\apps\api"
python D:\new_project\backend\cmd\worker.py
```

Env comes from `backend/apps/api/.env` (`REDIS_URL`, `POSTGRES_DSN`).
Without a running worker process, events stay `outbox_pending` / jobs `pending`
in Postgres even when Redis is healthy — API never drains the outbox.

Ops API parity:
- `/api/v1/ops/worker/run-batch` invokes bounded worker batch iterations for queue topology validation.
