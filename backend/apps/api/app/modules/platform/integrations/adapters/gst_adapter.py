from __future__ import annotations

from typing import Protocol

from app.modules.platform.integrations.adapters.canonical_models import CanonicalGSTReturn


class GstAdapter(Protocol):
    def to_canonical_gst_return(self, payload: dict) -> CanonicalGSTReturn: ...

