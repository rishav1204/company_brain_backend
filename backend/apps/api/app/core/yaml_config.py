from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ENV_VAR_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _backend_config_dir() -> Path:
    # backend/apps/api/app/core -> parents[4] == backend
    return Path(__file__).resolve().parents[4] / "config"


def _resolve_yaml_value(value: Any) -> Any:
    if isinstance(value, str):
        match = _ENV_VAR_PATTERN.match(value.strip())
        if match:
            return os.getenv(match.group(1), "")
        return value
    if isinstance(value, dict):
        return {key: _resolve_yaml_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_yaml_value(item) for item in value]
    return value


@lru_cache(maxsize=1)
def load_yaml_config() -> dict[str, Any]:
    env = os.getenv("APP_ENV", "dev").lower()
    filename = "prod.yaml" if env == "prod" else "dev.yaml"
    path = _backend_config_dir() / filename
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return _resolve_yaml_value(raw)


def yaml_get(*keys: str, default: Any = None) -> Any:
    node: Any = load_yaml_config()
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node if node is not None else default
