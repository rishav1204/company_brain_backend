#!/usr/bin/env python3
"""Bootstrap M36 API gateway — sample partner key + webhook subscription."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap M36 API gateway")
    parser.add_argument("--org-id", required=True)
    args = parser.parse_args()

    from app.modules.platform.api_gateway.services.api_key_service import api_key_service
    from app.modules.platform.api_gateway.services.webhook_service import webhook_service

    item, raw_key = api_key_service.create(
        args.org_id,
        name="bootstrap-partner-key",
        scopes=["invoice.read", "webhooks.manage", "reports.read"],
        key_tier="partner",
    )
    print(f"API key id={item.get('id')}")
    print(f"Raw key (save once): {raw_key}")

    sub, secret = webhook_service.create_subscription(
        args.org_id,
        endpoint_url="https://example.com/webhooks/finance",
        event_types=["invoice.created", "payment.executed"],
        name="bootstrap-webhook",
    )
    print(f"Webhook subscription id={sub.get('id')}")
    print(f"Webhook secret (save once): {secret}")


if __name__ == "__main__":
    main()
