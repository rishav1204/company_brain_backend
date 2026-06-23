from __future__ import annotations

from app.core.config import settings
from app.services.logger import log_event


class S3Provider:
    def put_object(self, *, object_key: str, raw_bytes: bytes, content_type: str) -> dict:
        bucket = settings.documents_s3_bucket.strip() or settings.textract_s3_bucket.strip()
        if not bucket:
            raise RuntimeError("DOCUMENTS_S3_BUCKET or TEXTRACT_S3_BUCKET must be configured for S3 storage")
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        client_kwargs: dict = {}
        if settings.aws_region:
            client_kwargs["region_name"] = settings.aws_region
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            if settings.aws_session_token:
                client_kwargs["aws_session_token"] = settings.aws_session_token
        client = boto3.client("s3", **client_kwargs)
        try:
            client.put_object(Bucket=bucket, Key=object_key, Body=raw_bytes, ContentType=content_type)
        except (ClientError, BotoCoreError) as exc:
            log_event("documents.s3.put.error", object_key=object_key, detail=str(exc))
            raise RuntimeError(f"S3 put failed: {exc}") from exc
        return {
            "object_key": object_key,
            "content_type": content_type,
            "size": len(raw_bytes),
            "provider": "s3",
            "bucket": bucket,
        }


s3_provider = S3Provider()
