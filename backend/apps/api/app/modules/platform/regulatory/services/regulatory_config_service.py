"""Mutating regulatory config for platform operators."""

from __future__ import annotations

from typing import Any

from app.modules.platform.regulatory.repositories.regulatory_repository import (
    regulatory_repository,
)
from app.modules.platform.regulatory.services.regulatory_resolver import (
    regulatory_resolver,
)


class RegulatoryConfigService:
    def list_params(self, **kwargs) -> list[dict[str, Any]]:
        return regulatory_repository.list_params(**kwargs)

    def upsert_param(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = regulatory_repository.upsert_param(payload, actor_id=actor_id)
        regulatory_repository.write_audit(
            actor_user_id=actor_id,
            entity_type="regulatory_param",
            entity_id=str(row.get("id") or payload.get("param_key")),
            action="upsert",
            org_id=payload.get("org_id"),
            after=row,
        )
        regulatory_resolver.clear_cache()
        return row

    def list_thresholds(self, **kwargs) -> list[dict[str, Any]]:
        return regulatory_repository.list_thresholds(**kwargs)

    def upsert_threshold(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = regulatory_repository.upsert_threshold(payload, actor_id=actor_id)
        regulatory_repository.write_audit(
            actor_user_id=actor_id,
            entity_type="regulatory_threshold",
            entity_id=str(row.get("id") or payload.get("threshold_code")),
            action="upsert",
            org_id=payload.get("org_id"),
            after=row,
        )
        regulatory_resolver.clear_cache()
        return row

    def list_penalties(self, **kwargs) -> list[dict[str, Any]]:
        return regulatory_repository.list_penalties(**kwargs)

    def upsert_penalty(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = regulatory_repository.upsert_penalty(payload, actor_id=actor_id)
        regulatory_repository.write_audit(
            actor_user_id=actor_id,
            entity_type="regulatory_penalty",
            entity_id=str(row.get("id") or payload.get("formula_code")),
            action="upsert",
            org_id=payload.get("org_id"),
            after=row,
        )
        regulatory_resolver.clear_cache()
        return row

    def list_slab_sets(self, **kwargs) -> list[dict[str, Any]]:
        return regulatory_repository.list_slab_sets(**kwargs)

    def upsert_slab_set(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = regulatory_repository.upsert_slab_set(payload)
        bands = payload.get("bands")
        if isinstance(bands, list) and row.get("id"):
            regulatory_repository.replace_slab_bands(row["id"], bands)
        regulatory_repository.write_audit(
            actor_user_id=actor_id,
            entity_type="regulatory_slab_set",
            entity_id=str(row.get("id") or payload.get("set_code")),
            action="upsert",
            org_id=payload.get("org_id"),
            after=row,
        )
        regulatory_resolver.clear_cache()
        return row

    def list_tds_templates(self) -> list[dict[str, Any]]:
        return regulatory_repository.list_tds_templates()

    def upsert_tds_template(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = regulatory_repository.upsert_tds_template(payload)
        regulatory_repository.write_audit(
            actor_user_id=actor_id,
            entity_type="regulatory_tds_template",
            entity_id=str(row.get("id") or payload.get("section_code")),
            action="upsert",
            after=row,
        )
        return row

    def apply_tds_templates(self, org_id: str, *, actor_id: str | None) -> dict[str, Any]:
        n = regulatory_repository.apply_tds_templates_to_org(org_id)
        regulatory_repository.write_audit(
            actor_user_id=actor_id,
            entity_type="regulatory_tds_template",
            entity_id=org_id,
            action="apply_to_org",
            org_id=org_id,
            after={"applied": n},
        )
        return {"org_id": org_id, "rows_touched": n}

    def list_compliance_templates(self) -> list[dict[str, Any]]:
        return regulatory_repository.list_compliance_templates()

    def preview(self, org_id: str | None, as_of: str | None) -> dict[str, Any]:
        return regulatory_resolver.effective_bundle(org_id=org_id, as_of=as_of)


regulatory_config_service = RegulatoryConfigService()
