#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
TARGETS = [
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

if __name__ == "__main__":
    script = REPO / "scripts" / "fix_unbounded_repos.py"
    text = script.read_text(encoding="utf-8")
    block = "TARGETS: list[str] = [\n" + "\n".join(f'    "{t}",' for t in TARGETS) + "\n]\n"
    text = text.replace("TARGETS: list[str] = []\n", block)
    script.write_text(text, encoding="utf-8")
    subprocess.check_call([sys.executable, str(script)], cwd=REPO)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "repair_pagination_codemod.py")], cwd=REPO)
    text = script.read_text(encoding="utf-8")
    text = text.replace(block, "TARGETS: list[str] = []\n")
    script.write_text(text, encoding="utf-8")
