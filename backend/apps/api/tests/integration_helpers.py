import os
import uuid

import pytest

ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "22222222-2222-4222-8222-222222222222"


def integration_infra_available() -> bool:
    return bool(os.getenv("POSTGRES_DSN")) and bool(os.getenv("REDIS_URL"))


def unique_key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
