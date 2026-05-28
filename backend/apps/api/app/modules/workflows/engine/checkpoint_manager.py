"""Persist workflow checkpoints in instance metadata."""

from __future__ import annotations


def save_checkpoint(metadata: dict | None, checkpoint: dict) -> dict:
    meta = dict(metadata or {})
    checkpoints = meta.get("checkpoints")
    if not isinstance(checkpoints, list):
        checkpoints = []
    checkpoints.append(checkpoint)
    meta["checkpoints"] = checkpoints[-50:]
    return meta
