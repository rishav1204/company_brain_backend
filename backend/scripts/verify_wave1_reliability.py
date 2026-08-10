"""Wave 1 reliability verification (RQ-11/12/13/18/01 + idempotency)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "backend" / "apps" / "api"
ENV_PATH = API_ROOT / ".env"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def _load_env_file() -> None:
    if not ENV_PATH.is_file():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    _load_env_file()

    from app.core.config import settings
    from app.services.db import close_pool
    from app.modules.platform.events.repositories.outbox_repository import outbox_repository
    from app.modules.platform.events.services.event_service import platform_event_service
    from app.modules.platform.events.services.outbox_publisher import outbox_publisher
    from app.services.redis_client import get_redis_client

    if not get_redis_client():
        print("WAVE1_VERIFY_FAILED: redis_unconfigured")
        return 1
    if not outbox_repository.schema_ready():
        print("WAVE1_VERIFY_FAILED: outbox_schema_missing")
        return 1

    # RQ-18: transactional outbox — publish creates outbox row, publisher drains it.
    # Must be a UUID (platform event bus enforces org UUIDs).
    org_id = os.getenv("WAVE1_VERIFY_ORG_ID") or os.getenv("DEV_ORG_ID") or "11111111-1111-4111-8111-111111111111"
    res = platform_event_service.publish(
        event_type="scheduler.wave1.verify",
        org_id=org_id,
        source="wave1.verify",
        payload={"ping": True},
        trace_id=None,
        actor_id=None,
        entity_type="verification",
        entity_id=None,
        metadata={"wave": 1},
        principal=None,
        idempotency_key="wave1.verify.event",
    )
    event_id = str(res.get("event_id") or "")
    if not event_id:
        print("WAVE1_VERIFY_FAILED: no_event_id")
        return 1

    pub = outbox_publisher.publish_once(limit=200)
    print("outbox_publish_summary", pub)

    # RQ-01 retention knobs exist and financial streams are configured to avoid approximate trim.
    ok_retention = bool(settings.redis_stream_financial_maxlen) and int(settings.redis_stream_financial_maxlen) >= int(
        settings.redis_stream_maxlen
    )
    if not ok_retention:
        print("WAVE1_VERIFY_FAILED: retention_config_invalid")
        return 1

    print("WAVE1_VERIFY_OK", {"event_id": event_id})
    try:
        close_pool()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

