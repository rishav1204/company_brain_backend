#!/usr/bin/env python3
"""Lightweight API latency benchmark for before/after comparisons."""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

import httpx


def _p95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[idx]


def bench(url: str, *, headers: dict[str, str] | None = None, iterations: int = 5) -> dict:
    samples: list[float] = []
    status = None
    with httpx.Client(timeout=60.0) as client:
        for _ in range(iterations):
            started = time.perf_counter()
            response = client.get(url, headers=headers or {})
            elapsed_ms = (time.perf_counter() - started) * 1000
            samples.append(elapsed_ms)
            status = response.status_code
    return {
        "url": url,
        "status": status,
        "iterations": iterations,
        "min_ms": min(samples),
        "max_ms": max(samples),
        "mean_ms": statistics.mean(samples),
        "p95_ms": _p95(samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark API latency endpoints")
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("API_BENCH_TOKEN", ""))
    parser.add_argument("--org-id", default=os.getenv("API_BENCH_ORG_ID", ""))
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    headers: dict[str, str] = {}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    if args.org_id:
        headers["x-org-id"] = args.org_id

    targets = [
        f"{base}/health",
        f"{base}/api/v1/iam/auth/login",
        f"{base}/api/v1/analytics/dashboard",
    ]

    print(f"Benchmarking {len(targets)} endpoints ({args.iterations} iterations each)\n")
    for url in targets:
        if "login" in url:
            print(f"SKIP {url} (POST login — use authenticated GET targets with --token)")
            continue
        try:
            result = bench(url, headers=headers, iterations=args.iterations)
        except Exception as exc:
            print(f"FAIL {url}: {exc}")
            continue
        print(
            f"{result['url']}\n"
            f"  status={result['status']} mean={result['mean_ms']:.1f}ms "
            f"p95={result['p95_ms']:.1f}ms min={result['min_ms']:.1f}ms max={result['max_ms']:.1f}ms\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
