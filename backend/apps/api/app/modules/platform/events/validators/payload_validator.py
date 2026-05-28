from __future__ import annotations

MAX_PAYLOAD_BYTES = 512_000


def validate_payload_size(payload: dict) -> None:
    import json

    size = len(json.dumps(payload, default=str).encode())
    if size > MAX_PAYLOAD_BYTES:
        raise ValueError(f"Event payload exceeds {MAX_PAYLOAD_BYTES} bytes")
