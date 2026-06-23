"""Document module service tests."""
from __future__ import annotations

from app.modules.platform.documents.ai.gst_extractor import gst_extractor


def test_gst_extractor_parses_amounts():
    text = "CGST 900.00 SGST 900.00 IGST 0.00 Total Amount 11800.00"
    result = gst_extractor.extract(text)
    assert result["cgst"] == 900.0
    assert result["sgst"] == 900.0
    assert result["total_amount"] == 11800.0


def test_thumbnail_worker_importable():
    from app.modules.platform.documents.workers.thumbnail_worker import process_thumbnail_job

    assert callable(process_thumbnail_job)
