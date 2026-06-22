from __future__ import annotations

from app.modules.erp.reporting.services.export_service import export_service


def run_export(org_id: str, *, run_id: str) -> dict:
    return export_service.process_run(org_id, run_id=run_id)
