from __future__ import annotations


def parse_pdf_metadata(file_name: str, raw_bytes: bytes) -> dict:
    return {
        "file_name": file_name,
        "size": len(raw_bytes),
        "pages_estimate": 1,
    }
