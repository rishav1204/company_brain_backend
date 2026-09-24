"""Resolve statute parameters from DB — engines must use this, not hardcodes."""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal
from typing import Any

from app.modules.platform.regulatory.repositories.regulatory_repository import (
    regulatory_repository,
)

_CACHE: dict[str, tuple[float, Any]] = {}
_TTL = 60.0


class RegulatoryConfigError(RuntimeError):
    """Raised when required regulatory config is missing from DB."""


class RegulatoryResolver:
    def _cache_get(self, key: str) -> Any | None:
        hit = _CACHE.get(key)
        if not hit:
            return None
        exp, val = hit
        if exp < time.time():
            _CACHE.pop(key, None)
            return None
        return val

    def _cache_set(self, key: str, val: Any) -> Any:
        _CACHE[key] = (time.time() + _TTL, val)
        return val

    def clear_cache(self) -> None:
        _CACHE.clear()

    def resolve_param(
        self,
        param_key: str,
        *,
        org_id: str | None = None,
        as_of: date | str | None = None,
        country_code: str = "IN",
        required: bool = True,
        default: Any = None,
    ) -> Any:
        ck = f"p:{country_code}:{org_id}:{param_key}:{as_of}"
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        row = regulatory_repository.resolve_param_row(
            param_key, org_id=org_id, as_of=as_of, country_code=country_code
        )
        if not row:
            if required and default is None:
                raise RegulatoryConfigError(f"Missing regulatory param: {param_key}")
            return default
        if row.get("value_numeric") is not None:
            val: Any = float(row["value_numeric"])
        elif row.get("value_text") is not None:
            val = row["value_text"]
        else:
            val = row.get("value_json") or {}
        return self._cache_set(ck, val)

    def resolve_param_numeric(
        self,
        param_key: str,
        *,
        org_id: str | None = None,
        as_of: date | str | None = None,
        required: bool = True,
        default: float | None = None,
    ) -> float:
        v = self.resolve_param(
            param_key, org_id=org_id, as_of=as_of, required=required, default=default
        )
        if v is None:
            if required:
                raise RegulatoryConfigError(f"Missing numeric regulatory param: {param_key}")
            return float(default or 0)
        return float(v)

    def resolve_threshold_amount(
        self,
        threshold_code: str,
        *,
        org_id: str | None = None,
        as_of: date | str | None = None,
        required: bool = True,
        default: float | None = None,
    ) -> float:
        ck = f"t:{org_id}:{threshold_code}:{as_of}"
        cached = self._cache_get(ck)
        if cached is not None:
            return float(cached)
        row = regulatory_repository.resolve_threshold(
            threshold_code, org_id=org_id, as_of=as_of
        )
        if not row:
            if required and default is None:
                raise RegulatoryConfigError(f"Missing regulatory threshold: {threshold_code}")
            val = float(default or 0)
            return self._cache_set(ck, val)
        val = float(row["amount"])
        return self._cache_set(ck, val)

    def resolve_allowed_gst_rates(
        self, *, org_id: str | None = None, as_of: date | str | None = None
    ) -> set[float]:
        row = regulatory_repository.resolve_param_row(
            "gst.allowed_rates", org_id=org_id, as_of=as_of
        )
        if row and isinstance(row.get("value_json"), list):
            return {float(x) for x in row["value_json"]}
        if row and isinstance(row.get("value_json"), dict):
            rates = row["value_json"].get("rates")
            if isinstance(rates, list):
                return {float(x) for x in rates}
        raise RegulatoryConfigError("Missing gst.allowed_rates regulatory param")

    def resolve_slab_bands(
        self,
        set_code: str | None = None,
        *,
        org_id: str | None = None,
        as_of: date | str | None = None,
    ) -> list[tuple[float | None, float]]:
        if not set_code:
            meta = self.resolve_param(
                "income_tax.default_slab_set",
                org_id=org_id,
                as_of=as_of,
                required=False,
                default="income_tax_new_regime",
            )
            if isinstance(meta, dict):
                set_code = str(meta.get("set_code") or "income_tax_new_regime")
            else:
                set_code = str(meta or "income_tax_new_regime")
        slab = regulatory_repository.resolve_slab_set(set_code, org_id=org_id, as_of=as_of)
        if not slab or not slab.get("bands"):
            raise RegulatoryConfigError(f"Missing slab set: {set_code}")
        out: list[tuple[float | None, float]] = []
        for b in slab["bands"]:
            upper = b.get("upper_limit")
            # rate_pct stored as percentage points (5 => 5%)
            rate = float(b.get("rate_pct") or 0) / 100.0
            out.append((float(upper) if upper is not None else None, rate))
        return out

    def resolve_penalty_formula(
        self,
        compliance_code: str,
        *,
        org_id: str | None = None,
        as_of: date | str | None = None,
    ) -> dict[str, Any]:
        row = regulatory_repository.resolve_penalty(
            compliance_code, org_id=org_id, as_of=as_of
        )
        if not row:
            raise RegulatoryConfigError(
                f"Missing penalty formula for compliance code: {compliance_code}"
            )
        return row

    def effective_bundle(
        self, *, org_id: str | None = None, as_of: date | str | None = None
    ) -> dict[str, Any]:
        keys = [
            "tds.no_pan_floor_pct",
            "income_tax.standard_deduction_annual",
            "income_tax.rebate_87a_amount",
            "income_tax.health_education_cess_pct",
            "gst.interest_delay_pct",
            "calendar.fy_start_month",
        ]
        params = {}
        for k in keys:
            try:
                params[k] = self.resolve_param(k, org_id=org_id, as_of=as_of, required=False)
            except RegulatoryConfigError:
                params[k] = None
        thresholds = {}
        for t in ("gst.b2c_large_invoice", "gst.eway_bill_min", "gst.einvoice_default"):
            try:
                thresholds[t] = self.resolve_threshold_amount(
                    t, org_id=org_id, as_of=as_of, required=False, default=None
                )
            except RegulatoryConfigError:
                thresholds[t] = None
        return {
            "org_id": org_id,
            "as_of": str(as_of or date.today()),
            "params": params,
            "thresholds": thresholds,
            "schema_ready": regulatory_repository.ready(),
        }


regulatory_resolver = RegulatoryResolver()
