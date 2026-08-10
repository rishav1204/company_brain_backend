from __future__ import annotations


def compute_risk_score(*, overdue: list[dict], escalations: list[dict], exposure: float) -> int:
    score = 0
    score += min(len(overdue) * 10, 40)
    score += min(len(escalations) * 8, 30)
    if exposure > 0:
        score += min(int(exposure / 10000), 30)
    return min(score, 100)


def detect_risks(*, obligations: list[dict], escalations: list[dict], exposure: float) -> dict:
    overdue = [o for o in obligations if o.get("status") == "overdue"]
    repeated = _repeated_delays(obligations)
    flags = []
    if overdue:
        flags.append({"type": "overdue", "count": len(overdue), "severity": "high"})
    if escalations:
        flags.append({"type": "open_escalations", "count": len(escalations), "severity": "high"})
    if repeated:
        flags.append({"type": "repeated_delays", "codes": repeated, "severity": "medium"})
    if exposure > 0:
        flags.append({"type": "penalty_exposure", "amount": exposure, "severity": "medium"})
    return {
        "risk_score": compute_risk_score(overdue=overdue, escalations=escalations, exposure=exposure),
        "flags": flags,
    }


def _repeated_delays(obligations: list[dict]) -> list[str]:
    from collections import Counter

    overdue_codes = [str(o.get("compliance_code")) for o in obligations if o.get("status") == "overdue"]
    counts = Counter(overdue_codes)
    return [code for code, cnt in counts.items() if cnt >= 2 and code]
