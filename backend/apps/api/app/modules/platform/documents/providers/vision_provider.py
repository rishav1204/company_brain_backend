from __future__ import annotations


class VisionProvider:
    def classify_visual(self, *, storage_path: str) -> dict:
        return {"label": "invoice", "confidence": 0.7, "provider": "vision_stub", "storage_path": storage_path}


vision_provider = VisionProvider()
