"""Run production connector configuration + connectivity UAT (ERP-17/19/20)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "backend" / "apps" / "api"
ENV_PATH = API_ROOT / ".env"
SCRIPT_DIR = Path(__file__).resolve().parent
MOCK_SERVER = SCRIPT_DIR / "connector_uat_mock_server.py"

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


def _apply_mock_env(urls: dict[str, str]) -> None:
    os.environ["INTEGRATIONS_MODE"] = "production"
    os.environ["GSTN_BASE_URL"] = urls["gst"]
    os.environ["GSTN_API_KEY"] = os.environ.get("GSTN_API_KEY", "uat-mock-gstn-key")
    os.environ["NSDL_TDS_BASE_URL"] = urls["tds"]
    os.environ["NSDL_TDS_TAN"] = os.environ.get("NSDL_TDS_TAN", "UATB00001A")
    os.environ["NSDL_TDS_USER"] = os.environ.get("NSDL_TDS_USER", "uat_tds_user")
    os.environ["NSDL_TDS_PASSWORD"] = os.environ.get("NSDL_TDS_PASSWORD", "uat_tds_password")
    os.environ["BANK_API_BASE_URL"] = urls["bank"]
    os.environ["BANK_API_KEY"] = os.environ.get("BANK_API_KEY", "uat-mock-bank-key")


def _start_mock_server() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(MOCK_SERVER)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    line = proc.stdout.readline() if proc.stdout else ""
    if not line.strip():
        raise RuntimeError("connector UAT mock server failed to start")
    urls = json.loads(line.strip())
    time.sleep(0.2)
    return proc, urls


def main() -> int:
    parser = argparse.ArgumentParser(description="ERP-17/19/20 connector UAT")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Force INTEGRATIONS_MODE=production (fail if connectors missing/unreachable)",
    )
    parser.add_argument(
        "--with-mock",
        action="store_true",
        help="Start local /health mock servers and configure env for UAT",
    )
    args = parser.parse_args()

    _load_env_file()
    mock_proc = None
    if args.with_mock:
        mock_proc, urls = _start_mock_server()
        _apply_mock_env(urls)
    elif args.production:
        os.environ["INTEGRATIONS_MODE"] = "production"

    try:
        import app.modules.platform.integrations.connectors  # noqa: F401
        from app.modules.platform.integrations.services.connector_uat_service import connector_uat_service

        result = connector_uat_service.run_all(require_reachable=True)
        print(json.dumps(result, indent=2))
        if result.get("mode") == "stub" and args.production:
            print("CONNECTOR_UAT_FAILED — INTEGRATIONS_MODE still stub; use --with-mock or set env vars.")
            return 1
        if result.get("mode") == "stub":
            print("UAT skipped (stub mode). Use --production --with-mock or configure GSTN/NSDL/BANK env vars.")
            return 0
        if not result.get("passed"):
            print("CONNECTOR_UAT_FAILED — configure missing env vars in backend/apps/api/.env")
            return 1
        print("CONNECTOR_UAT_OK")
        return 0
    finally:
        if mock_proc is not None:
            mock_proc.terminate()
            try:
                mock_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mock_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
