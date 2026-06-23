#!/usr/bin/env python3
"""Add LIMIT + clamp_limit to repository methods with unbounded fetchall()."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "apps" / "api" / "app"
DEFAULT_LIMIT = 500

TARGETS: list[str] = []


def _file_has_unbounded(text: str) -> bool:
    blocks = re.split(r"cur\.execute\(", text)
    for block in blocks[1:]:
        snippet = block[:900]
        if "fetchall()" in snippet and "LIMIT" not in snippet.upper():
            return True
    return False


def _inject_limit_in_sql(sql: str) -> str:
    if "LIMIT" in sql.upper():
        return sql
    stripped = sql.rstrip()
    return stripped + "\n                    LIMIT %s\n                    "


def _fix_function_source(src: str, func_name: str) -> str:
    if "fetchall()" not in src:
        return src
    if "LIMIT" in src and "LIMIT %s" in src:
        # may still be unbounded if different execute block
        pass
    # Add clamp_limit import usage at function start if we add limit param
    m = re.match(r"(def\s+\w+\([^)]*)\)", src, re.DOTALL)
    if not m:
        return src
    sig = m.group(1)
    if "limit" not in sig:
        if sig.rstrip().endswith("("):
            new_sig = sig + f"*, limit: int = {DEFAULT_LIMIT}"
        else:
            new_sig = sig + f", *, limit: int = {DEFAULT_LIMIT}"
    else:
        new_sig = sig
    body = src[m.end() :]
    if "clamp_limit" not in body:
        body = body.replace(":\n", ":\n        limit = clamp_limit(limit)\n", 1)
    # Fix SQL blocks in this function
    def sql_repl(match: re.Match[str]) -> str:
        sql = match.group(1)
        rest = match.group(2)
        if "fetchall()" not in rest[:400]:
            return match.group(0)
        if "LIMIT" in sql.upper():
            return match.group(0)
        new_sql = _inject_limit_in_sql(sql)
        return f'"""\n{new_sql}"""' + rest

    body = re.sub(
        r'"""(.*?)"""(\s*,\s*\([^)]*\)\s*,?)',
        sql_repl,
        body,
        flags=re.DOTALL,
    )
    # Fix param tuples: add limit before closing paren of execute
    body = re.sub(
        r"(\(\s*org_id[^)]*)\)(\s*\)\s*\n\s*return[^f]*fetchall)",
        lambda m: m.group(1) + ", limit)" + m.group(2) if ", limit" not in m.group(1) else m.group(0),
        body,
        flags=re.DOTALL,
    )
    return new_sig + "):" + body


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if not _file_has_unbounded(text):
        return False
    if "from app.services.repository_pagination import clamp_limit" not in text:
        # insert after future import or at top
        if "from __future__" in text:
            text = re.sub(
                r"(from __future__ import annotations\n)",
                r"\1\nfrom app.services.repository_pagination import clamp_limit\n",
                text,
                count=1,
            )
        else:
            text = "from app.services.repository_pagination import clamp_limit\n" + text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    lines = text.splitlines(keepends=True)
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    changed = False
    for func in reversed(funcs):
        if func.end_lineno is None:
            continue
        chunk = "".join(lines[func.lineno - 1 : func.end_lineno])
        if "fetchall()" not in chunk:
            continue
        if "LIMIT %s" in chunk and "clamp_limit" in chunk:
            continue
        # Simple line-based fix for ORDER BY ... fetchall pattern
        new_chunk = chunk
        if "ORDER BY" in chunk or "fetchall()" in chunk:
            if "LIMIT %s" not in chunk:
                new_chunk = re.sub(
                    r"(\n\s*\"\"\",\s*\n)",
                    "\n                    LIMIT %s\n\\1",
                    new_chunk,
                    count=1,
                ) if "LIMIT %s" not in new_chunk else new_chunk
                if "LIMIT %s" not in new_chunk:
                    new_chunk = re.sub(
                        r"(\n\s*\"\"\",\s*\n)",
                        "\n                    LIMIT %s\n\\1",
                        new_chunk,
                        count=1,
                    )
            if "limit: int" not in new_chunk.split("def ", 1)[1].split(")", 1)[0]:
                new_chunk = re.sub(
                    r"(def \w+\([^)]*)\)",
                    r"\1, *, limit: int = 500)",
                    new_chunk,
                    count=1,
                )
            if "clamp_limit" not in new_chunk:
                new_chunk = re.sub(
                    r"(\):\n)(\s+)",
                    r"\1\2limit = clamp_limit(limit)\n\2",
                    new_chunk,
                    count=1,
                )
            new_chunk = re.sub(
                r"(\(\s*org_id[^)]*)(\)\s*\)\s*\n\s*return[^\n]*fetchall)",
                lambda m: m.group(1) + ", limit)" + m.group(2)[1:]
                if ", limit" not in m.group(1)
                else m.group(0),
                new_chunk,
                count=1,
            )
        if new_chunk != chunk:
            lines[func.lineno - 1 : func.end_lineno] = [new_chunk]
            changed = True
    if changed:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def main() -> int:
    fixed = 0
    targets = [APP / p.replace("/", "\\") for p in TARGETS] if TARGETS else []
    paths = targets if targets else sorted(APP.rglob("**/repositories/*.py"))
    for py in paths:
        if not py.exists():
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        if _file_has_unbounded(text):
            if fix_file(py):
                fixed += 1
                print("fixed", py.relative_to(REPO))
    print(f"fixed {fixed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
