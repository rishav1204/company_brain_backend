#!/usr/bin/env python3
"""Repair pagination codemod artifacts."""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "apps" / "api" / "app"


def repair_signatures(text: str) -> str:
    text = text.replace(", *, limit: int = 500", ", limit: int = 500")
    text = re.sub(r",\s*\n\s*, limit: int = 500\)", ",\n        limit: int = 500,\n    )", text)
    text = re.sub(
        r"(\n\s+)(company_id: str \| None = None,)\n(\s+), limit: int = 500\)",
        r"\1\2,\n\3limit: int = 500,\n\3)",
        text,
    )
    return text


def repair_limit_params(text: str) -> str:
    # After LIMIT %s in SQL, ensure tuple includes limit variable
    pattern = re.compile(
        r'(LIMIT %s\s*""",\s*\n\s*)(\([^)]+\))(\s*\)\s*\n\s*return[^\n]*fetchall)',
        re.MULTILINE,
    )

    def repl(m: re.Match[str]) -> str:
        params = m.group(2)
        if ", limit" in params or params.rstrip().endswith("limit)"):
            return m.group(0)
        inner = params.strip()[1:-1].strip()
        if not inner:
            new_params = "(limit,)"
        else:
            new_params = f"({inner}, limit)"
        return m.group(1) + new_params + m.group(3)

    return pattern.sub(repl, text)


def main() -> None:
    for py in APP.rglob("**/*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        new = repair_limit_params(repair_signatures(text))
        if new != text:
            py.write_text(new, encoding="utf-8")
            print("repaired", py.relative_to(REPO))

    reasoner = APP / "modules" / "finance_os" / "agents" / "ai" / "finance_reasoner.py"
    reasoner.write_text(
        '''from __future__ import annotations

from app.modules.finance_os.agents.schemas.agents_schema import AgentContext


def summarize(context: AgentContext) -> str:
    parts = [f"Agent {context.agent_name}", f"task={context.task_type}"]
    if context.entity_id:
        parts.append(f"entity={context.entity_id}")
    parts.append(f"memory={len(context.memory_snippets)} graph={len(context.graph_paths)}")
    return "; ".join(parts)
''',
        encoding="utf-8",
    )
    print("repaired finance_reasoner")


if __name__ == "__main__":
    main()
