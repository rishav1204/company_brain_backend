from __future__ import annotations


def load_compliance(org_id: str) -> dict:
    from app.modules.erp.compliance.services.compliance_dashboard_service import compliance_dashboard_service

    dash = compliance_dashboard_service.build(org_id)
    all_open = len(dash.get("today") or []) + len(dash.get("upcoming_7d") or []) + len(dash.get("overdue") or [])
    overdue = len(dash.get("overdue") or [])
    completed_proxy = max(all_open, 1)
    filing_pct = round(max(0.0, (completed_proxy - overdue) / completed_proxy * 100.0), 2) if all_open else 100.0
    return {
        "filing_compliance_pct": filing_pct,
        "penalty_exposure": float(dash.get("penalty_exposure_total") or 0),
        "risk_score": float(dash.get("risk_score") or 0),
        "overdue_count": overdue,
        "escalations_open": len(dash.get("escalations_open") or []),
    }
