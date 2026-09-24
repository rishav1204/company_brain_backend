from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import (
    ConversationState,
    EntityCandidate,
    EntityResolutionResult,
    ResolvedEntity,
)
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState

_PERIOD_PATTERNS = [
    (re.compile(r"\bq([1-4])\s*fy\s*(\d{4})\b", re.I), lambda m: f"Q{m.group(1)}-FY{m.group(2)}"),
    (re.compile(r"\blast quarter\b", re.I), lambda _: "last_quarter"),
    (re.compile(r"\bthis quarter\b", re.I), lambda _: "current_quarter"),
    (re.compile(r"\blast month\b", re.I), lambda _: "last_month"),
    (re.compile(r"\bthis month\b", re.I), lambda _: "current_month"),
]

_ENTITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "gst": ("gst", "cgst", "sgst", "igst", "tax return"),
    "vendor": ("vendor", "supplier"),
    "invoice": ("invoice", "bill"),
    "customer": ("customer", "client"),
    "po": ("purchase order", " po ", "po-"),
    "grn": ("grn", "goods receipt"),
    "bank": ("bank", "account balance"),
    "period": ("fiscal period", "financial year", "fy "),
    "asset": ("asset", "fixed asset"),
    "employee": ("employee", "staff", "payroll"),
    "voucher": ("voucher", "journal voucher"),
    "claim": ("expense claim", "reimbursement"),
}

_ALIASES: dict[str, tuple[str, ...]] = {
    "vendor": ("supplier", "payee", "creditor"),
    "customer": ("client", "debtor", "buyer"),
    "invoice": ("bill", "ap invoice", "tax invoice"),
    "po": ("purchase order", "p.o.", "purchaseorder"),
    "grn": ("goods receipt", "goods receipt note", "receipt note"),
}


class EntityResolver:
    """Entity Resolver V2 — ranked candidates with confidence threshold (AI-02)."""

    def resolve(
        self,
        message: str,
        *,
        world_state: WorldState | None = None,
        working_memory: ConversationState | None = None,
        org_id: str | None = None,
    ) -> list[ResolvedEntity]:
        result = self.resolve_v2(
            message,
            world_state=world_state,
            working_memory=working_memory,
            org_id=org_id,
        )
        return result.entities

    def resolve_v2(
        self,
        message: str,
        *,
        world_state: WorldState | None = None,
        working_memory: ConversationState | None = None,
        org_id: str | None = None,
    ) -> EntityResolutionResult:
        threshold = float(settings.m38_entity_confidence_threshold)
        min_margin = float(settings.m38_entity_min_margin)
        candidates: list[EntityCandidate] = []
        text = (message or "").lower()
        ws = world_state
        wm = working_memory or ConversationState()

        def add_candidate(
            *,
            entity_type: str,
            entity_id: str | None,
            label: str | None,
            score: float,
            match_type: str,
            source: str,
        ) -> None:
            score = max(0.0, min(1.0, score))
            score = self._context_boost(score, entity_type=entity_type, entity_id=entity_id, world_state=ws, working_memory=wm)
            candidates.append(
                EntityCandidate(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    label=label,
                    score=round(score, 4),
                    match_type=match_type,
                    source=source,
                )
            )

        # High-confidence UI / selection context (exact / context bindings)
        if ws and ws.screen and ws.screen.entity_type:
            add_candidate(
                entity_type=ws.screen.entity_type,
                entity_id=ws.screen.entity_id,
                label=ws.screen.entity_type,
                score=0.97 if ws.screen.entity_id else 0.8,
                match_type="exact" if ws.screen.entity_id else "context",
                source="screen",
            )
        if ws and ws.selection:
            for key, val in ws.selection.items():
                if not val:
                    continue
                etype = key.replace("_id", "") if key.endswith("_id") else key
                add_candidate(
                    entity_type=etype,
                    entity_id=str(val),
                    label=etype,
                    score=0.93,
                    match_type="exact",
                    source="selection",
                )
        if ws and ws.org:
            if ws.org.company_id:
                add_candidate(
                    entity_type="company",
                    entity_id=ws.org.company_id,
                    label="company",
                    score=0.9,
                    match_type="context",
                    source="org",
                )
            if ws.org.branch_id:
                add_candidate(
                    entity_type="branch",
                    entity_id=ws.org.branch_id,
                    label="branch",
                    score=0.9,
                    match_type="context",
                    source="org",
                )
            if ws.org.fiscal_period_id:
                add_candidate(
                    entity_type="period",
                    entity_id=ws.org.fiscal_period_id,
                    label="fiscal_period",
                    score=0.9,
                    match_type="context",
                    source="org",
                )

        if wm.current_entity:
            add_candidate(
                entity_type=str(wm.current_entity.get("type") or "entity"),
                entity_id=wm.current_entity.get("id"),
                label=str(wm.current_entity.get("label") or ""),
                score=0.86,
                match_type="context",
                source="working_memory",
            )
        if wm.current_vendor_id:
            add_candidate(
                entity_type="vendor",
                entity_id=wm.current_vendor_id,
                label="vendor",
                score=0.86,
                match_type="context",
                source="working_memory",
            )
        if wm.current_period:
            add_candidate(
                entity_type="period",
                entity_id=wm.current_period,
                label=wm.current_period,
                score=0.82,
                match_type="context",
                source="working_memory",
            )

        # Keyword / alias type hints (no id → not auto-binding)
        for entity_type, keywords in _ENTITY_KEYWORDS.items():
            if any(k in text for k in keywords):
                add_candidate(
                    entity_type=entity_type,
                    entity_id=None,
                    label=entity_type,
                    score=0.62,
                    match_type="alias",
                    source="nlp_keyword",
                )
        for entity_type, aliases in _ALIASES.items():
            if any(a in text for a in aliases):
                add_candidate(
                    entity_type=entity_type,
                    entity_id=None,
                    label=entity_type,
                    score=0.64,
                    match_type="alias",
                    source="nlp_alias",
                )

        for pattern, fmt in _PERIOD_PATTERNS:
            m = pattern.search(message or "")
            if m:
                label = fmt(m)
                add_candidate(
                    entity_type="period",
                    entity_id=label,
                    label=label,
                    score=0.78,
                    match_type="exact",
                    source="nlp_period",
                )
                break

        id_match = re.search(r"\b([a-z]{2,5}[-_][\w-]+)\b", message or "", re.I)
        if id_match:
            token = id_match.group(1)
            etype = self._infer_type_from_token(token)
            # Structured document codes (INV-001, PO-ACME-001, …) are strong exact refs
            structured = bool(re.match(r"^(inv|po|grn|ap|ar)[-_]", token, re.I))
            add_candidate(
                entity_type=etype,
                entity_id=token,
                label=token.upper() if structured else token,
                score=0.95 if structured else 0.78,
                match_type="exact",
                source="nlp_id",
            )

        # Optional code lookup (org-isolated) when possible
        if org_id and id_match:
            self._enrich_from_erp(org_id, candidates, token=id_match.group(1), message=text)

        # Fuzzy match against recent entities / selection labels
        for recent in (ws.recent_entities if ws else []) or []:
            rtype = str(recent.get("type") or recent.get("entity_type") or "entity")
            rid = recent.get("id") or recent.get("entity_id")
            rlabel = str(recent.get("label") or recent.get("name") or rid or "")
            if not rlabel:
                continue
            ratio = SequenceMatcher(None, text, rlabel.lower()).ratio()
            if ratio >= 0.55 or rlabel.lower() in text:
                add_candidate(
                    entity_type=rtype,
                    entity_id=str(rid) if rid else None,
                    label=rlabel,
                    score=0.55 + 0.35 * ratio,
                    match_type="fuzzy",
                    source="recent_entities",
                )

        # Deduplicate by type+id (same entity from multiple sources → best score only)
        best: dict[str, EntityCandidate] = {}
        for c in candidates:
            key = f"{c.entity_type}:{c.entity_id or c.label or c.source}"
            prev = best.get(key)
            if not prev or c.score > prev.score:
                best[key] = c
        ranked = sorted(best.values(), key=lambda c: c.score, reverse=True)

        entities: list[ResolvedEntity] = []
        needs_clarification = False
        clarification_prompt: str | None = None

        # Group by entity_type for ambiguity detection when selecting ids
        by_type: dict[str, list[EntityCandidate]] = {}
        for c in ranked:
            if c.entity_id:
                by_type.setdefault(c.entity_type, []).append(c)

        for etype, group in by_type.items():
            # Collapse identical entity_id to one candidate (max score)
            unique: dict[str, EntityCandidate] = {}
            for c in group:
                eid = str(c.entity_id)
                prev = unique.get(eid)
                if not prev or c.score > prev.score:
                    unique[eid] = c
            group = list(unique.values())
            # Also collapse document-code vs UUID for the same label (INV-001 vs uuid)
            by_label: dict[str, EntityCandidate] = {}
            for c in group:
                lab = (c.label or "").strip().lower() or str(c.entity_id).lower()
                prev = by_label.get(lab)
                if not prev:
                    by_label[lab] = c
                    continue
                prefer = c
                # Prefer real UUID ids over raw document codes when labels match
                c_uuid = self._looks_uuid(c.entity_id)
                p_uuid = self._looks_uuid(prev.entity_id)
                if c_uuid and not p_uuid:
                    prefer = c
                elif p_uuid and not c_uuid:
                    prefer = prev
                elif c.score > prev.score:
                    prefer = c
                else:
                    prefer = prev
                by_label[lab] = prefer
            group = sorted(by_label.values(), key=lambda c: c.score, reverse=True)
            top = group[0]
            second = group[1] if len(group) > 1 else None
            margin = (top.score - second.score) if second else 1.0
            # Exact single document-code match: bind even if slightly under global threshold
            exact_solo = (
                len(group) == 1
                and top.match_type == "exact"
                and top.score >= min(threshold, 0.70)
            )
            ambiguous = bool(second and margin < min_margin and second.score >= threshold * 0.9)
            below = top.score < threshold and not exact_solo
            if below or ambiguous:
                needs_clarification = True
                if len(group) == 1:
                    clarification_prompt = (
                        f"I found a possible {etype} reference “{top.label or top.entity_id}” "
                        f"(confidence {top.score:.2f}). Reply with the exact document number "
                        f"to continue (for example: INV-001)."
                    )
                else:
                    clarification_prompt = (
                        f"Multiple {etype} candidates found. "
                        f"Please clarify which {etype} you mean (top scores: "
                        + ", ".join(f"{g.label or g.entity_id}:{g.score:.2f}" for g in group[:3])
                        + ")."
                    )
                # Do not bind entity_id below threshold / when ambiguous
                entities.append(
                    ResolvedEntity(
                        entity_type=etype,
                        entity_id=None,
                        label=top.label,
                        source=top.source,
                        confidence=top.score,
                        needs_clarification=True,
                        candidates=group[:5],
                        match_type=top.match_type,
                    )
                )
            else:
                entities.append(
                    ResolvedEntity(
                        entity_type=etype,
                        entity_id=top.entity_id,
                        label=top.label,
                        source=top.source,
                        confidence=top.score,
                        needs_clarification=False,
                        candidates=group[:5],
                        match_type=top.match_type,
                    )
                )

        # Type-only entities (no id yet)
        for c in ranked:
            if c.entity_id:
                continue
            if any(e.entity_type == c.entity_type for e in entities):
                continue
            if c.score >= threshold:
                entities.append(
                    ResolvedEntity(
                        entity_type=c.entity_type,
                        entity_id=None,
                        label=c.label,
                        source=c.source,
                        confidence=c.score,
                        match_type=c.match_type,
                        candidates=[c],
                    )
                )
            else:
                entities.append(
                    ResolvedEntity(
                        entity_type=c.entity_type,
                        entity_id=None,
                        label=c.label,
                        source=c.source,
                        confidence=c.score,
                        match_type=c.match_type,
                        candidates=[c],
                        needs_clarification=False,
                    )
                )

        return EntityResolutionResult(
            entities=entities,
            candidates=ranked[:20],
            needs_clarification=needs_clarification,
            clarification_prompt=clarification_prompt,
            threshold=threshold,
        )

    def _context_boost(
        self,
        score: float,
        *,
        entity_type: str,
        entity_id: str | None,
        world_state: WorldState | None,
        working_memory: ConversationState,
    ) -> float:
        boost = 0.0
        if world_state and world_state.screen and world_state.screen.entity_type == entity_type:
            boost += 0.05
            if entity_id and world_state.screen.entity_id == entity_id:
                boost += 0.05
        if working_memory.current_vendor_id and entity_type == "vendor" and entity_id == working_memory.current_vendor_id:
            boost += 0.04
        if world_state and world_state.org and world_state.org.fiscal_period_id and entity_type == "period":
            if entity_id == world_state.org.fiscal_period_id:
                boost += 0.05
        return min(1.0, score + boost)

    def _infer_type_from_token(self, token: str) -> str:
        t = token.lower()
        if t.startswith("po"):
            return "po"
        if t.startswith("grn"):
            return "grn"
        if t.startswith("vch") or t.startswith("jv") or t.startswith("pv") or t.startswith("rv"):
            return "voucher"
        if t.startswith("inv") or t.startswith("ap") or t.startswith("ar"):
            return "invoice"
        if t.startswith("ven") or t.startswith("sup"):
            return "vendor"
        return "entity"

    @staticmethod
    def _looks_uuid(value: str | None) -> bool:
        if not value:
            return False
        return bool(
            re.match(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                str(value),
                re.I,
            )
        )

    def _enrich_from_erp(self, org_id: str, candidates: list[EntityCandidate], *, token: str, message: str) -> None:
        """Best-effort exact code lookups (org-isolated). Failures are non-fatal."""
        code = (token or "").strip()
        if not code:
            return
        # AP / AR invoice number → real UUID (so get_invoice can bind)
        try:
            from app.services.db import get_db_conn, set_rls_org

            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id::text, invoice_number, 'ap' AS src
                        FROM erp.ap_invoices
                        WHERE org_id = %s::uuid AND lower(invoice_number) = lower(%s)
                        LIMIT 2
                        """,
                        (org_id, code),
                    )
                    ap_rows = cur.fetchall() or []
                    if len(ap_rows) == 1:
                        row = dict(ap_rows[0])
                        candidates.append(
                            EntityCandidate(
                                entity_type="invoice",
                                entity_id=str(row["id"]),
                                label=str(row.get("invoice_number") or code),
                                score=0.98,
                                match_type="exact",
                                source="erp_ap_invoice",
                            )
                        )
                    cur.execute(
                        """
                        SELECT id::text, invoice_number
                        FROM erp.ar_invoices
                        WHERE org_id = %s::uuid AND lower(invoice_number) = lower(%s)
                        LIMIT 2
                        """,
                        (org_id, code),
                    )
                    ar_rows = cur.fetchall() or []
                    if len(ar_rows) == 1 and not ap_rows:
                        row = dict(ar_rows[0])
                        candidates.append(
                            EntityCandidate(
                                entity_type="invoice",
                                entity_id=str(row["id"]),
                                label=str(row.get("invoice_number") or code),
                                score=0.98,
                                match_type="exact",
                                source="erp_ar_invoice",
                            )
                        )
        except Exception:
            pass
        try:
            from app.modules.erp.query_services import inventory_queries

            item = inventory_queries.get_item_by_code(org_id, item_code=code.upper())
            if item:
                candidates.append(
                    EntityCandidate(
                        entity_type="item",
                        entity_id=str(item.get("id")),
                        label=str(item.get("item_name") or code),
                        score=0.92,
                        match_type="exact",
                        source="erp_code",
                    )
                )
        except Exception:
            pass


entity_resolver = EntityResolver()
