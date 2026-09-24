"""Fix repository cur.execute calls that have LIMIT %s but omit limit from params."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "api" / "app"
IMPORT_LINE = "from app.services.repository_pagination import clamp_limit"


def _param_count(params: str) -> int:
    depth = 0
    parts: list[str] = []
    cur: list[str] = []
    for ch in params.strip():
        if ch in "([{":
            depth += 1
            cur.append(ch)
        elif ch in ")]}":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return len([p for p in parts if p])


def _ensure_import(text: str) -> str:
    if IMPORT_LINE in text:
        return text
    if "from __future__ import annotations" in text:
        return text.replace(
            "from __future__ import annotations\n",
            f"from __future__ import annotations\n\n{IMPORT_LINE}\n",
            1,
        )
    return IMPORT_LINE + "\n" + text


def fix_text(text: str) -> tuple[str, int]:
    patterns = [
        re.compile(
            r'cur\.execute\(\s*(?P<q>""")(?P<sql>.*?LIMIT %s.*?)(?P=q)\s*,\s*\((?P<params>.*?)\)\s*\)',
            re.S,
        ),
        re.compile(
            r"cur\.execute\(\s*(?P<q>''')(?P<sql>.*?LIMIT %s.*?)(?P=q)\s*,\s*\((?P<params>.*?)\)\s*\)",
            re.S,
        ),
    ]
    fixes = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal fixes
        sql = m.group("sql")
        params = m.group("params")
        q = m.group("q")
        placeholders = len(re.findall(r"(?<!%)%s", sql))
        if re.search(r"\blimit\b", params, re.I) or "clamp_limit" in params:
            return m.group(0)
        if placeholders <= _param_count(params):
            return m.group(0)
        params_stripped = params.strip()
        if params_stripped.endswith(","):
            new_params = params_stripped + " clamp_limit(limit)"
        elif params_stripped:
            new_params = params_stripped + ", clamp_limit(limit)"
        else:
            new_params = "clamp_limit(limit)"
        fixes += 1
        return f"cur.execute(\n                    {q}{sql}{q},\n                    ({new_params}),\n                )"

    out = text
    for pat in patterns:
        out = pat.sub(repl, out)
    if fixes:
        out = _ensure_import(out)
    return out, fixes


def main() -> None:
    files = 0
    sites = 0
    for path in ROOT.rglob("*.py"):
        original = path.read_text(encoding="utf-8")
        updated, n = fix_text(original)
        if n:
            path.write_text(updated, encoding="utf-8")
            files += 1
            sites += n
            print(f"fixed {path.relative_to(ROOT)} ({n})")
    print(f"DONE files={files} sites={sites}")


if __name__ == "__main__":
    main()
