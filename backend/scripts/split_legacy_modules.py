#!/usr/bin/env python3
"""One-time helper: relocate legacy monolith modules to package paths with shims."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "apps" / "api" / "app"

HANDLERS_SRC = APP / "services" / "event_consumers_handlers.py"
HANDLERS_DST_DIR = APP / "modules" / "platform" / "events" / "consumers" / "handlers"
HANDLERS_DST = HANDLERS_DST_DIR / "legacy_handlers.py"

REPOS_SRC = APP / "services" / "repositories.py"
REPOS_DST_DIR = APP / "services" / "legacy_repos"
REPOS_DST = REPOS_DST_DIR / "legacy_repositories.py"


def relocate_handlers() -> None:
    if not HANDLERS_SRC.exists():
        return
    text = HANDLERS_SRC.read_text(encoding="utf-8")
    if "legacy_handlers" in text and len(text.splitlines()) < 300:
        print("handlers already shimed")
        return
    HANDLERS_DST_DIR.mkdir(parents=True, exist_ok=True)
    HANDLERS_DST.write_text(text, encoding="utf-8")
    (HANDLERS_DST_DIR / "__init__.py").write_text(
        '"""Event consumer handler implementations (migrated from app.services)."""\n',
        encoding="utf-8",
    )
    shim = '''"""Compatibility shim — handlers live in platform.events.consumers.handlers."""
from app.modules.platform.events.consumers.handlers.legacy_handlers import *  # noqa: F403
'''
    HANDLERS_SRC.write_text(shim, encoding="utf-8")
    print(f"Relocated handlers -> {HANDLERS_DST}")


def relocate_repos() -> None:
    if not REPOS_SRC.exists():
        return
    text = REPOS_SRC.read_text(encoding="utf-8")
    if "legacy_repositories" in text and len(text.splitlines()) < 50:
        print("repos already shimed")
        return
    REPOS_DST_DIR.mkdir(parents=True, exist_ok=True)
    REPOS_DST.write_text(text, encoding="utf-8")
    (REPOS_DST_DIR / "__init__.py").write_text(
        '"""Legacy repository implementations."""\n',
        encoding="utf-8",
    )
    shim = '''"""Compatibility shim — repositories live in app.services.legacy_repos."""
from app.services.legacy_repos.legacy_repositories import *  # noqa: F403
'''
    REPOS_SRC.write_text(shim, encoding="utf-8")
    print(f"Relocated repositories -> {REPOS_DST}")


if __name__ == "__main__":
    relocate_handlers()
    relocate_repos()
