from __future__ import annotations

from app.modules.platform.events.services.scheduling_service import scheduling_service


def run_scheduler_emissions(org_id: str) -> dict:
    return scheduling_service.run_org_scheduled_emissions(org_id)
