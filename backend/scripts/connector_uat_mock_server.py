"""Minimal HTTP health servers for connector UAT (GST/TDS/Bank)."""
from __future__ import annotations

import json
import signal
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

DEFAULT_PORTS = {"gst": 9101, "tds": 9102, "bank": 9103}


class _HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            body = json.dumps({"status": "ok", "service": "connector_uat_mock"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def main() -> int:
    ports = DEFAULT_PORTS.copy()
    if len(sys.argv) > 1:
        ports["gst"] = int(sys.argv[1])
    if len(sys.argv) > 2:
        ports["tds"] = int(sys.argv[2])
    if len(sys.argv) > 3:
        ports["bank"] = int(sys.argv[3])

    servers: list[HTTPServer] = []
    for name, port in ports.items():
        server = HTTPServer(("127.0.0.1", port), _HealthHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)

    urls = {name: f"http://127.0.0.1:{port}" for name, port in ports.items()}
    print(json.dumps(urls), flush=True)

    def _shutdown(*_args) -> None:
        for server in servers:
            server.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        _shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
