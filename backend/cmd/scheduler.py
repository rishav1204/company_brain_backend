import time

from app.core.config import settings
from app.services.scheduler_service import run_scheduled_jobs_once


def main() -> None:
    org_ids = [item.strip() for item in settings.scheduler_org_ids.split(",") if item.strip()]
    if not org_ids:
        org_ids = ["org-demo"]
    while True:
        for org_id in org_ids:
            run_scheduled_jobs_once(org_id=org_id)
        time.sleep(60)


if __name__ == "__main__":
    main()
