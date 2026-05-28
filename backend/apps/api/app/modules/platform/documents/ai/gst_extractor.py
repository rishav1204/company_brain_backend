from __future__ import annotations


class GSTExtractor:
    def extract(self, text: str) -> dict:
        # Placeholder GST extraction; can be replaced with model-backed parser.
        return {
            "subtotal": 0.0,
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": 0.0,
            "cess": 0.0,
            "total_amount": 0.0,
            "raw_text_preview": text[:2000],
        }


gst_extractor = GSTExtractor()
