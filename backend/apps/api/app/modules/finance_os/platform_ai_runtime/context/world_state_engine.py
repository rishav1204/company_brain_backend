"""World State Engine — merge UI publishes with persisted session state (Wave 4)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import (
    WorldState,
    WorldStateOrg,
    WorldStateScreen,
)
from app.services.logger import log_event


def _merge_dict(base: dict, overlay: dict) -> dict:
    out = dict(base or {})
    for k, v in (overlay or {}).items():
        if v is None or v == "" or v == [] or v == {}:
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def _sync_selection_aliases(data: dict) -> dict:
    """Map screen entity + selection into convenience fields."""
    sel = data.get("selection") if isinstance(data.get("selection"), dict) else {}
    screen = data.get("screen") if isinstance(data.get("screen"), dict) else {}
    etype = str(screen.get("entity_type") or "").lower()
    eid = screen.get("entity_id")
    if eid and etype:
        if etype in {"invoice", "ap_invoice"}:
            data.setdefault("current_invoice_id", eid)
            sel.setdefault("invoice_id", eid)
        elif etype == "vendor":
            data.setdefault("current_vendor_id", eid)
            sel.setdefault("vendor_id", eid)
        elif etype == "customer":
            data.setdefault("current_customer_id", eid)
            sel.setdefault("customer_id", eid)
        elif etype == "journal":
            data.setdefault("current_journal_id", eid)
            sel.setdefault("journal_id", eid)
        elif etype in {"po", "purchase_order"}:
            data.setdefault("current_po_id", eid)
            sel.setdefault("po_id", eid)
        elif etype == "workflow":
            data.setdefault("current_workflow_id", eid)
        elif etype == "approval":
            data.setdefault("current_approval_id", eid)
    for key, field in (
        ("invoice_id", "current_invoice_id"),
        ("vendor_id", "current_vendor_id"),
        ("customer_id", "current_customer_id"),
        ("journal_id", "current_journal_id"),
        ("po_id", "current_po_id"),
        ("workflow_id", "current_workflow_id"),
        ("approval_id", "current_approval_id"),
    ):
        if sel.get(key):
            data[field] = sel[key]
    data["selection"] = sel
    return data


class WorldStateEngine:
    """Canonical world state merge / persistence. Frontend publishes; backend stores."""

    def from_payload(
        self,
        *,
        payload: dict | None = None,
        roles: list[str] | None = None,
        explicit: WorldState | None = None,
    ) -> WorldState:
        if explicit is not None:
            data = explicit.model_dump()
        else:
            payload = payload or {}
            raw = payload.get("world_state") if isinstance(payload.get("world_state"), dict) else payload
            data = dict(raw or {})
        if roles:
            data["roles"] = list(roles)
            if not data.get("permissions"):
                data["permissions"] = list(roles)
        data = _sync_selection_aliases(data)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            return WorldState(**data)
        except Exception:
            # Tolerant parse for partial UI payloads
            return WorldState(
                screen=WorldStateScreen(**(data.get("screen") or {})) if data.get("screen") else None,
                org=WorldStateOrg(**(data.get("org") or {})) if data.get("org") else None,
                selection=data.get("selection") or {},
                permissions=list(data.get("permissions") or roles or []),
                roles=list(data.get("roles") or roles or []),
            )

    def merge(self, base: WorldState | None, update: WorldState | None) -> WorldState:
        if not base and not update:
            return WorldState()
        if not base:
            return update or WorldState()
        if not update:
            return base
        merged = _merge_dict(base.model_dump(), update.model_dump())
        merged = _sync_selection_aliases(merged)
        # Track navigation breadcrumb
        nav = list(merged.get("recent_navigation") or [])
        us = update.screen
        if us and (us.route or us.module):
            entry = {
                "module": us.module,
                "route": us.route,
                "entity_type": us.entity_type,
                "entity_id": us.entity_id,
                "at": datetime.now(timezone.utc).isoformat(),
            }
            nav.append(entry)
            merged["recent_navigation"] = nav[-20:]
        # Recently viewed objects
        viewed = list(merged.get("recently_viewed") or [])
        if us and us.entity_id:
            viewed.append(
                {
                    "entity_type": us.entity_type,
                    "entity_id": us.entity_id,
                    "title": us.title,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            )
            # dedupe keep last
            seen: set[str] = set()
            deduped: list[dict] = []
            for item in reversed(viewed):
                key = f"{item.get('entity_type')}:{item.get('entity_id')}"
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(item)
            merged["recently_viewed"] = list(reversed(deduped))[-15:]
        merged["updated_at"] = datetime.now(timezone.utc).isoformat()
        return WorldState(**merged)

    def load_persisted(self, org_id: str, goal_id: str | None) -> WorldState | None:
        if not goal_id:
            return None
        goal = goal_repository.get_goal(org_id, goal_id)
        if not goal:
            return None
        raw = goal.get("world_state")
        if not isinstance(raw, dict) or not raw:
            return None
        try:
            return WorldState(**raw)
        except Exception:
            return None

    def resolve(
        self,
        org_id: str,
        *,
        published: WorldState | None,
        goal_id: str | None = None,
        roles: list[str] | None = None,
    ) -> WorldState:
        """Merge UI publish over persisted goal world state — source of truth for context."""
        persisted = self.load_persisted(org_id, goal_id)
        incoming = self.from_payload(explicit=published, roles=roles) if published else None
        if persisted and incoming:
            return self.merge(persisted, incoming)
        if incoming:
            return incoming
        if persisted:
            return persisted
        return WorldState(roles=list(roles or []), permissions=list(roles or []))

    def publish(
        self,
        org_id: str,
        world_state: WorldState,
        *,
        goal_id: str | None = None,
        user_id: str | None = None,
    ) -> WorldState:
        resolved = self.resolve(org_id, published=world_state, goal_id=goal_id)
        if goal_id:
            goal_repository.update_world_state(org_id, goal_id, resolved.model_dump())
        log_event(
            "m38.world_state.published",
            org_id=org_id,
            goal_id=goal_id or "",
            user_id=user_id or "",
            module=(resolved.screen.module if resolved.screen else None),
            entity_type=(resolved.screen.entity_type if resolved.screen else None),
            entity_id=(resolved.screen.entity_id if resolved.screen else None),
        )
        return resolved


world_state_engine = WorldStateEngine()
