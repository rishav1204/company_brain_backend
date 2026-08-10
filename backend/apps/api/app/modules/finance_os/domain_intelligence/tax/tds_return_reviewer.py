from __future__ import annotations


def review_return_payload(*, payload: dict, form_type: str) -> dict:
    checks: list[dict] = []
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}

    if not sections:
        checks.append({"level": "error", "code": "empty_sections", "message": "No section rows in return payload"})
    if float(summary.get("total_tax") or summary.get("total_tds") or 0) <= 0:
        checks.append({"level": "warning", "code": "zero_tax", "message": "Return shows zero TDS/TCS — verify before filing"})

    for sec in sections:
        if int(sec.get("count") or 0) == 0:
            checks.append({
                "level": "warning",
                "code": "empty_section",
                "message": f"Section {sec.get('section_code')} has zero transactions",
            })

    if form_type.upper() == "24Q":
        note = str(summary.get("note") or "")
        if note and int(summary.get("transaction_count") or 0) == 0:
            checks.append({"level": "warning", "code": "no_salary_tds", "message": note})

    blocking = [c for c in checks if c["level"] == "error"]
    return {
        "ready_to_file": len(blocking) == 0,
        "checks": checks,
        "check_count": len(checks),
    }
