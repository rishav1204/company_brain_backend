#!/usr/bin/env python3
"""Restore cur.execute( removed by broken pagination codemod."""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "apps" / "api" / "app"

BROKEN = [
    "modules/core/iam/repositories/organization_repository.py",
    "modules/core/iam/repositories/permission_repository.py",
    "modules/core/iam/repositories/role_repository.py",
    "modules/erp/inventory/repositories/movement_repository.py",
    "modules/erp/procurement/repositories/grn_repository.py",
    "modules/erp/tax/repositories/compliance_repository.py",
    "modules/erp/tax/repositories/gst_repository.py",
    "modules/erp/tax/repositories/itc_repository.py",
    "modules/erp/tax/repositories/return_repository.py",
    "modules/erp/tax/repositories/tds_return_repository.py",
    "modules/finance_os/agents/repositories/execution_repository.py",
    "modules/finance_os/memory/repositories/entry_repository.py",
    "modules/finance_os/memory/repositories/reference_repository.py",
    "modules/finance_os/workflow_intelligence/repositories/stage_metric_repository.py",
    "modules/platform/billing/repositories/billing_repository.py",
    "modules/platform/documents/repositories/extraction_repository.py",
    "modules/platform/integrations/repositories/api_key_repository.py",
    "modules/platform/integrations/repositories/webhook_repository.py",
]


def repair(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if "with conn.cursor() as cur:" in line:
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                out.append(lines[j])
                j += 1
            if j < len(lines):
                nxt = lines[j].lstrip()
                if nxt.startswith('"""') or nxt.startswith('f"""'):
                    indent = re.match(r"^(\s*)", lines[j]).group(1)
                    out.append(f"{indent}cur.execute(\n")
        i += 1
    text = "".join(out)
    # Remove erroneous limit param on update methods
    text = re.sub(
        r"(def update_\w+\([^)]*),\s*limit: int = 500,",
        r"\1,",
        text,
    )
    text = re.sub(
        r"(def update_\w+\([^)]*)\n\s*limit: int = 500,\n",
        r"\1\n",
        text,
    )
    return text


def main() -> None:
    for rel in BROKEN:
        path = APP / rel.replace("/", "\\")
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        fixed = repair(original)
        if fixed != original:
            path.write_text(fixed, encoding="utf-8")
            print("restored", rel)


if __name__ == "__main__":
    main()
