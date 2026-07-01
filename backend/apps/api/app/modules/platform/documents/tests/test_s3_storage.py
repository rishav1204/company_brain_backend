"""S3 storage and Textract connector tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.platform.documents.providers.s3_provider import (
    format_s3_storage_path,
    parse_s3_storage_path,
    s3_provider,
)
from app.modules.platform.documents.services.storage_service import storage_service


def test_parse_s3_storage_path_valid() -> None:
    assert parse_s3_storage_path("s3://my-bucket/finance-docs/org/invoice/2026/01/01/file.pdf") == (
        "my-bucket",
        "finance-docs/org/invoice/2026/01/01/file.pdf",
    )


def test_parse_s3_storage_path_invalid() -> None:
    assert parse_s3_storage_path("cloudinary://cloud/raw/id") is None
    assert parse_s3_storage_path("s3://bucket-only") is None


def test_format_s3_storage_path() -> None:
    assert format_s3_storage_path(bucket="b", object_key="k") == "s3://b/k"


def test_storage_service_upload_s3(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "documents_s3_bucket", "docs-bucket")
    monkeypatch.setattr(settings, "documents_bucket_prefix", "finance-docs")

    with patch.object(s3_provider, "put_object") as mock_put:
        mock_put.return_value = {
            "bucket": "docs-bucket",
            "object_key": "finance-docs/org1/invoice/2026/06/23/a.pdf",
            "content_type": "application/pdf",
            "size": 4,
            "provider": "s3",
        }
        result = storage_service.upload(
            org_id="org1",
            document_type="invoice",
            file_name="a.pdf",
            raw_bytes=b"test",
            mime_type="application/pdf",
        )

    assert result["provider"] == "s3"
    assert result["storage_path"].startswith("s3://docs-bucket/")
    mock_put.assert_called_once()


def test_storage_service_signed_download_url_s3(monkeypatch) -> None:
    with patch.object(s3_provider, "get_presigned_url", return_value="https://signed.example/obj") as mock_url:
        url = storage_service.signed_download_url("s3://docs-bucket/finance-docs/org/a.pdf")
    assert url == "https://signed.example/obj"
    mock_url.assert_called_once_with(
        bucket="docs-bucket",
        object_key="finance-docs/org/a.pdf",
        expires_in_seconds=900,
    )


def test_storage_service_preview_urls_s3() -> None:
    with patch.object(storage_service, "signed_download_url", return_value="https://signed.example/obj"):
        previews = storage_service.preview_urls(
            "s3://docs-bucket/finance-docs/org/a.pdf",
            mime_type="application/pdf",
        )
    assert previews["download_url"] == "https://signed.example/obj"
    assert previews["thumbnail_url"] == "https://signed.example/obj"
    assert previews["preview_url"] == "https://signed.example/obj"


def test_resolved_storage_provider_auto_prefers_s3(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "storage_provider", "auto")
    monkeypatch.setattr(settings, "documents_s3_bucket", "docs-bucket")
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "cloud")
    monkeypatch.setattr(settings, "cloudinary_api_key", "key")
    monkeypatch.setattr(settings, "cloudinary_api_secret", "secret")
    assert settings.resolved_storage_provider() == "s3"


def test_textract_staging_key() -> None:
    key = s3_provider.staging_key_for_textract(source_bucket="docs", source_key="finance-docs/org/file.pdf")
    assert key == "textract-staging/docs/finance-docs/org/file.pdf"


def test_textract_extract_from_s3_async(monkeypatch) -> None:
    from app.core.config import settings
    from app.modules.platform.integrations.connectors.ocr.textract_impl import TextractOcrImpl

    monkeypatch.setattr(settings, "aws_region", "ap-south-1")
    monkeypatch.setattr(settings, "textract_s3_bucket", "textract-bucket")
    monkeypatch.setattr(settings, "documents_s3_bucket", "docs-bucket")

    impl = TextractOcrImpl()
    mock_textract = MagicMock()
    mock_textract.start_document_text_detection.return_value = {"JobId": "job-1"}
    mock_textract.get_document_text_detection.return_value = {
        "JobStatus": "SUCCEEDED",
        "Blocks": [{"BlockType": "LINE", "Text": "Invoice 123", "Page": 1}],
    }

    with (
        patch.object(impl, "_textract_client", return_value=mock_textract),
        patch.object(s3_provider, "copy_object") as mock_copy,
        patch.object(
            storage_service,
            "signed_download_url",
            return_value="https://signed.example/obj",
        ),
    ):
        result = impl.extract_text(
            storage_path="s3://docs-bucket/finance-docs/org1/invoice/file.pdf",
            mime_type="application/pdf",
        )

    mock_copy.assert_called_once()
    assert result["provider"] == "aws_textract"
    assert "Invoice 123" in result["text"]
