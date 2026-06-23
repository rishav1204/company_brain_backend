#!/usr/bin/env python3
"""Add LIMIT %s to remaining unbounded SELECT fetchall blocks."""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "apps" / "api" / "app"

TARGETS = [
    "modules/platform/billing/repositories/billing_repository.py",
    "modules/platform/documents/repositories/extraction_repository.py",
    "modules/platform/integrations/repositories/api_key_repository.py",
    "modules/platform/integrations/repositories/webhook_repository.py",
    "modules/finance_os/agents/repositories/execution_repository.py",
    "modules/finance_os/memory/repositories/entry_repository.py",
    "modules/finance_os/memory/repositories/reference_repository.py",
    "modules/finance_os/workflow_intelligence/repositories/stage_metric_repository.py",
    "modules/erp/inventory/repositories/movement_repository.py",
    "modules/erp/procurement/repositories/grn_repository.py",
    "modules/erp/tax/repositories/compliance_repository.py",
    "modules/erp/tax/repositories/gst_repository.py",
    "modules/erp/tax/repositories/itc_repository.py",
    "modules/erp/tax/repositories/return_repository.py",
    "modules/erp/tax/repositories/tds_return_repository.py",
    "modules/core/iam/repositories/organization_repository.py",
    "modules/core/iam/repositories/permission_repository.py",
    "modules/core/iam/repositories/role_repository.py",
]


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "from app.services.repository_pagination import clamp_limit" not in text:
        if "from __future__" in text:
            text = re.sub(
                r"(from __future__ import annotations\n)",
                r"\1\nfrom app.services.repository_pagination import clamp_limit\n",
                text,
                count=1,
            )
        else:
            text = "from app.services.repository_pagination import clamp_limit\n" + text
    changed = False
    parts = text.split("cur.execute(")
    rebuilt = [parts[0]]
    for block in parts[1:]:
        chunk = "cur.execute(" + block
        segment = block[:1200]
        if "fetchall()" in segment and "LIMIT" not in segment.upper():
            block = re.sub(
                r"(\n\s*\"\"\",\s*\n\s*)(\()",
                r"\n                    LIMIT %s\n\1\2",
                block,
                count=1,
            )
            if "limit = clamp_limit" not in block[:400]:
                block = re.sub(
                    r"(def [^\n]+\):\n)(\s+)",
                    r"\1\2limit = clamp_limit(limit)\n\2",
                    block,
                    count=1,
                )
            block = re.sub(
                r"(def [^(]+\([^)]*)\) ->",
                lambda m: m.group(1) + ", *, limit: int = 500) ->"
                if "limit:" not in m.group(1)
                else m.group(0),
                block,
                count=1,
            )
            block = re.sub(
                r"(\(\s*org_id[^)]*)(\)\s*\)\s*\n\s*return[^\n]*fetchall)",
                lambda m: m.group(1) + ", limit)" + m.group(2)[1:]
                if ", limit" not in m.group(1)
                else m.group(0),
                block,
                count=1,
            )
            changed = True
        rebuilt.append(block)
    new_text = "".join(rebuilt)
    if changed:
        path.write_text(new_text, encoding="utf-8")
    return changed


def main() -> None:
    for rel in TARGETS:
        path = APP / rel.replace("/", "\\")
        if path.exists() and fix_file(path):
            print("fixed", rel)


if __name__ == "__main__":
    main()
