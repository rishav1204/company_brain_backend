from __future__ import annotations

from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.modules.erp.procurement.repositories.po_repository import po_repository


class VendorSelectionService:
    def recommend(self, org_id: str, *, item_hint: str = "", limit: int = 5) -> list[dict]:
        vendors = vendor_repository.list(org_id, status="active", limit=50)
        scored: list[tuple[float, dict]] = []
        hint = item_hint.lower()
        for v in vendors:
            score = 0.0
            meta = v.get("metadata") if isinstance(v.get("metadata"), dict) else {}
            if meta.get("preferred"):
                score += 10
            name = str(v.get("vendor_name") or "").lower()
            if hint and hint in name:
                score += 5
            vid = str(v.get("id") or "")
            pos = po_repository.list(org_id, vendor_id=vid, limit=20)
            if pos:
                score += min(len(pos), 5)
                avg = sum(float(p.get("total_amount") or 0) for p in pos) / len(pos)
                score += max(0, 5 - avg / 100000)
            scored.append((score, v))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "vendor_id": str(v.get("id")),
                "vendor_name": v.get("vendor_name"),
                "vendor_code": v.get("vendor_code"),
                "score": round(s, 2),
                "preferred": bool((v.get("metadata") or {}).get("preferred") if isinstance(v.get("metadata"), dict) else False),
            }
            for s, v in scored[:limit]
        ]


vendor_selection_service = VendorSelectionService()
