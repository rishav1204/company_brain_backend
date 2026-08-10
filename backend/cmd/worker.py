"""Background queue worker.

Run from anywhere with:

  set PYTHONPATH=backend/apps/api   (PowerShell: $env:PYTHONPATH=...)
  python backend/cmd/worker.py

Requires REDIS_URL and POSTGRES_DSN (loaded from backend/apps/api/.env).
The HTTP API alone never drains queues — only this process (or
POST /ops/worker/run-*) does.
"""
import time

from app.core.config import settings
from app.services.logger import log_event
from app.services.redis_client import get_redis_client
from app.services.worker_service import run_queue_worker_batch


def main() -> None:
    client = get_redis_client()
    if client is None:
        raise SystemExit(
            "REDIS_URL is not set (worker cannot drain queues). "
            "Set it in backend/apps/api/.env and restart."
        )
    try:
        client.ping()
    except Exception as exc:
        raise SystemExit(f"Redis unreachable: {exc}") from exc

    log_event(
        "worker.started",
        redis_ok=True,
        event_queue_backend=settings.event_queue_backend,
        worker_boundary=settings.worker_service_boundary or "all",
    )
    while True:
        summary = run_queue_worker_batch(iterations=50)
        log_event(
            "worker.batch.done",
            processed_iterations=summary.get("processed_iterations"),
            empty_iterations=summary.get("empty_iterations"),
            retry_iterations=summary.get("retry_iterations"),
            dlq_iterations=summary.get("dlq_iterations"),
        )
        time.sleep(1)


if __name__ == "__main__":
    main()
