#!/usr/bin/env python3
"""Smoke test for M38 Platform Copilot against a running API."""
from __future__ import annotations

import json
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    with httpx.Client(timeout=120.0) as client:
        r = client.get(f"{BASE}/health")
        check("GET /health", r.status_code == 200 and r.json().get("status") == "ok", str(r.status_code))

        r = client.get(f"{BASE}/ready")
        body = r.json()
        mig = (body.get("checks") or {}).get("migrations", "")
        check("GET /ready", r.status_code == 200 and body.get("status") == "ready", f"migrations={mig}")

        r = client.get(f"{BASE}/api/v1/finance-os/runtime/health")
        m38 = r.json()
        # health may require auth in some builds; accept 401 before login
        m38_ok = r.status_code == 200 and m38.get("schema_ready") is True
        check(
            "GET /finance-os/runtime/health (pre-auth)",
            m38_ok or r.status_code == 401,
            json.dumps(m38) if r.status_code == 200 else f"status={r.status_code}",
        )

        token = None
        for path in ("/api/v1/auth/login", "/api/v1/auth/password/login"):
            r = client.post(f"{BASE}{path}", json={"email": "dev@example.com", "password": "dev-password"})
            if r.status_code == 200 and r.json().get("access_token"):
                token = r.json()["access_token"]
                check(f"POST {path}", True, "token obtained")
                break
        if not token:
            check("POST auth login", False, f"status={r.status_code} body={r.text[:300]}")
            return 1

        headers = {"Authorization": f"Bearer {token}"}

        r = client.get(f"{BASE}/api/v1/finance-os/runtime/health", headers=headers)
        m38_auth = r.json()
        check(
            "GET /finance-os/runtime/health (auth)",
            r.status_code == 200 and m38_auth.get("schema_ready") is True,
            json.dumps(m38_auth),
        )

        r = client.post(
            f"{BASE}/api/v1/finance-os/copilot/chat",
            headers=headers,
            json={"message": "Show inventory balances on hand", "human_approved": False},
        )
        chat = r.json()
        ok_chat = r.status_code == 200 and bool(chat.get("goal_id")) and chat.get("mode") in {"answer", "completed", "executing"}
        check(
            "POST /copilot/chat (read/answer)",
            ok_chat,
            f"status={chat.get('status')} mode={chat.get('mode')} nodes={len(chat.get('graph_nodes') or [])}",
        )

        r2 = client.post(
            f"{BASE}/api/v1/finance-os/copilot/chat",
            headers=headers,
            json={"message": "Buy 5 laptops from vendor for inventory", "human_approved": False},
        )
        chat2 = r2.json()
        ok_proc = r2.status_code == 200 and chat2.get("approval_required") is True
        check(
            "POST /copilot/chat (procurement approval)",
            ok_proc,
            f"status={chat2.get('status')} approval_required={chat2.get('approval_required')} "
            f"progress={chat2.get('progress_percent')}",
        )

        r3 = client.get(f"{BASE}/api/v1/finance-os/runtime/approvals", headers=headers)
        appr = r3.json()
        check("GET /runtime/approvals", r3.status_code == 200 and "items" in appr, f"count={appr.get('count')}")

        r4 = client.get(f"{BASE}/api/v1/finance-os/runtime/tools", headers=headers)
        tools = r4.json()
        tool_count = len(tools.get("tools") or [])
        check("GET /runtime/tools", r4.status_code == 200 and tool_count >= 100, f"tools={tool_count}")

    failed = [n for n, ok, _ in results if not ok]
    print()
    print("=== SMOKE TEST SUMMARY ===")
    print(f"Passed: {sum(1 for _, ok, _ in results if ok)}/{len(results)}")
    if failed:
        print("Failed:", ", ".join(failed))
        return 1
    print("All smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
