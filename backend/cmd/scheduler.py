import time

from app.core.config import settings
from app.core.redis_lock import redis_lock
from app.services.scheduler_service import run_scheduled_jobs_once


def main() -> None:
    org_ids = [item.strip() for item in settings.scheduler_org_ids.split(",") if item.strip()]
    if not org_ids:
        org_ids = ["org-demo"]
    while True:
        # RQ-13: Leader election — exactly one active scheduler across instances.
        # Lease renews while loop runs; failover occurs on lease expiry.
        with redis_lock("scheduler:leader", ttl_seconds=45, wait_seconds=1.0, renew=True, renew_interval_seconds=15.0):
            for org_id in org_ids:
                run_scheduled_jobs_once(org_id=org_id)
        time.sleep(60)


if __name__ == "__main__":
    main()
