"""CI gate: no statute hardcodes in production engines."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "api" / "app"

# Banned symbols (production engines only)
BANNED = [
    (r"DEFAULT_GST_RATES\s*=", "gst DEFAULT_GST_RATES constant"),
    (r"INDIA_FY_SLABS\s*=", "income tax INDIA_FY_SLABS constant"),
    (r"STANDARD_DEDUCTION_ANNUAL\s*=", "STANDARD_DEDUCTION_ANNUAL constant"),
    (r"B2C_LARGE_THRESHOLD\s*=", "B2C_LARGE_THRESHOLD constant"),
    (r"max\(float\(rate_no_pan\),\s*20\.0\)", "inline no-PAN 20.0 floor"),
    (r"taxable_value\s*<\s*50000", "hardcoded e-way 50000"),
]

SCAN_GLOBS = [
    "modules/erp/tax/engine/**/*.py",
    "modules/erp/tax/services/eway_bill_service.py",
    "modules/erp/payroll/services/tds_calculator.py",
    "modules/erp/compliance/engine/penalty_engine.py",
]


def main() -> int:
    failures: list[str] = []
    for pattern in SCAN_GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for rx, label in BANNED:
                if re.search(rx, text):
                    failures.append(f"{path.relative_to(ROOT)}: {label}")
    if failures:
        print("Regulatory hardcode gate failed:")
        for f in failures:
            print(" -", f)
        return 1
    print("regulatory hardcode gate OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
