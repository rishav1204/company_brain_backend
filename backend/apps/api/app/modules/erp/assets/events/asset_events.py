from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


def emit_asset_created(org_id: str, *, asset_id: str, asset_code: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="asset.created",
        source="erp.assets",
        payload={"asset_id": asset_id, "asset_code": asset_code},
    )


def emit_asset_capitalized(org_id: str, *, asset_id: str, journal_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="asset.capitalized",
        source="erp.assets",
        payload={"asset_id": asset_id, "journal_id": journal_id},
    )


def emit_asset_depreciated(org_id: str, *, asset_id: str, amount: float, period_key: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="asset.depreciated",
        source="erp.assets",
        payload={"asset_id": asset_id, "amount": amount, "period_key": period_key},
    )


def emit_asset_transferred(org_id: str, *, asset_id: str, transfer_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="asset.transferred",
        source="erp.assets",
        payload={"asset_id": asset_id, "transfer_id": transfer_id},
    )


def emit_asset_disposed(org_id: str, *, asset_id: str, gain_loss: float) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="asset.disposed",
        source="erp.assets",
        payload={"asset_id": asset_id, "gain_loss": gain_loss},
    )


def emit_asset_impaired(org_id: str, *, asset_id: str, impairment_amount: float) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="asset.impaired",
        source="erp.assets",
        payload={"asset_id": asset_id, "impairment_amount": impairment_amount},
    )


def emit_candidate_detected(org_id: str, *, candidate_id: str, source_type: str, source_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="asset.candidate.detected",
        source="erp.assets",
        payload={"candidate_id": candidate_id, "source_type": source_type, "source_id": source_id},
    )
