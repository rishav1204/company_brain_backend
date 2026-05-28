import argparse
import os

import httpx


def _auth_headers() -> dict[str, str]:
    org_id = os.getenv("SMOKE_ORG_ID", "11111111-1111-4111-8111-111111111111")
    user_id = os.getenv("SMOKE_USER_ID", "smoke-user")
    roles = os.getenv("SMOKE_ROLES", "tenant_admin")
    token = os.getenv("SMOKE_BEARER_TOKEN", "").strip()
    headers = {
        "X-Org-Id": org_id,
        "X-User-Id": user_id,
        "X-Roles": roles,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def run(base_url: str, check_observability: bool = True) -> int:
    root = base_url.rstrip("/")
    checks = [
        (f"{root}/health", {"status": "ok"}, {}),
        (f"{root}/ready", {"status": "ready"}, {}),
    ]
    for url, expected_subset, headers in checks:
        response = httpx.get(url, timeout=10.0, headers=headers)
        if response.status_code != 200:
            print(f"Smoke check failed for {url}: status={response.status_code}")
            return 1
        payload = response.json()
        for key, expected in expected_subset.items():
            if payload.get(key) != expected:
                print(f"Smoke check failed for {url}: {key}={payload.get(key)!r} expected {expected!r}")
                return 1
        print(f"Smoke check passed: {url}")

    if check_observability:
        auth_headers = _auth_headers()
        metrics_url = f"{root}/api/v1/metrics"
        metrics_response = httpx.get(metrics_url, timeout=10.0, headers=auth_headers)
        if metrics_response.status_code != 200:
            print(f"Smoke check failed for {metrics_url}: status={metrics_response.status_code}")
            return 1
        metrics_body = metrics_response.json()
        if "metrics" not in metrics_body:
            print("Smoke check failed: /metrics response missing metrics block")
            return 1
        print(f"Smoke check passed: {metrics_url}")

        prom_url = f"{root}/api/v1/metrics/prometheus"
        prom_response = httpx.get(prom_url, timeout=10.0, headers=auth_headers)
        if prom_response.status_code != 200:
            print(f"Smoke check failed for {prom_url}: status={prom_response.status_code}")
            return 1
        prom_text = prom_response.text
        for required in ("app_request_count", "app_otel_enabled", "app_log_sink_configured"):
            if required not in prom_text:
                print(f"Smoke check failed: prometheus output missing {required}")
                return 1
        print(f"Smoke check passed: {prom_url}")

        status_url = f"{root}/api/v1/observability/status"
        status_response = httpx.get(status_url, timeout=10.0, headers=auth_headers)
        if status_response.status_code != 200:
            print(f"Smoke check failed for {status_url}: status={status_response.status_code}")
            return 1
        status_body = status_response.json()
        if status_body.get("verification_status") != "observability_stack_status":
            print("Smoke check failed: observability status verification marker missing")
            return 1
        print(f"Smoke check passed: {status_url}")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--skip-observability", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(base_url=args.base_url, check_observability=not args.skip_observability))
