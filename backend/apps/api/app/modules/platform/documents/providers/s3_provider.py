from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.logger import log_event


def parse_s3_storage_path(storage_path: str) -> tuple[str, str] | None:
    """Parse s3://bucket/key into (bucket, key). Returns None if not an S3 path."""
    path = (storage_path or "").strip()
    if not path.lower().startswith("s3://"):
        return None
    rest = path[5:]
    if "/" not in rest:
        return None
    bucket, key = rest.split("/", 1)
    if not bucket or not key:
        return None
    return bucket, key


def format_s3_storage_path(*, bucket: str, object_key: str) -> str:
    return f"s3://{bucket}/{object_key}"


class S3Provider:
    def _client_kwargs(self) -> dict[str, Any]:
        client_kwargs: dict[str, Any] = {}
        if settings.aws_region:
            client_kwargs["region_name"] = settings.aws_region
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            if settings.aws_session_token:
                client_kwargs["aws_session_token"] = settings.aws_session_token
        return client_kwargs

    def _client(self):
        import boto3

        return boto3.client("s3", **self._client_kwargs())

    def documents_bucket(self) -> str:
        bucket = settings.documents_s3_bucket.strip() or settings.textract_s3_bucket.strip()
        if not bucket:
            raise RuntimeError("DOCUMENTS_S3_BUCKET or TEXTRACT_S3_BUCKET must be configured for S3 storage")
        return bucket

    def textract_bucket(self) -> str:
        bucket = settings.textract_s3_bucket.strip() or settings.documents_s3_bucket.strip()
        if not bucket:
            raise RuntimeError("TEXTRACT_S3_BUCKET or DOCUMENTS_S3_BUCKET must be configured for Textract")
        return bucket

    def put_object(
        self,
        *,
        object_key: str,
        raw_bytes: bytes,
        content_type: str,
        bucket: str | None = None,
    ) -> dict:
        target_bucket = bucket or self.documents_bucket()
        client = self._client()
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            client.put_object(
                Bucket=target_bucket,
                Key=object_key,
                Body=raw_bytes,
                ContentType=content_type,
            )
        except (ClientError, BotoCoreError) as exc:
            log_event("documents.s3.put.error", object_key=object_key, detail=str(exc))
            raise RuntimeError(f"S3 put failed: {exc}") from exc
        return {
            "object_key": object_key,
            "content_type": content_type,
            "size": len(raw_bytes),
            "provider": "s3",
            "bucket": target_bucket,
        }

    def get_presigned_url(
        self,
        *,
        bucket: str,
        object_key: str,
        expires_in_seconds: int = 900,
    ) -> str:
        client = self._client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=max(60, int(expires_in_seconds)),
        )

    def get_object_bytes(self, *, bucket: str, object_key: str) -> bytes:
        client = self._client()
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            response = client.get_object(Bucket=bucket, Key=object_key)
            return response["Body"].read()
        except (ClientError, BotoCoreError) as exc:
            log_event("documents.s3.get.error", object_key=object_key, detail=str(exc))
            raise RuntimeError(f"S3 get failed: {exc}") from exc

    def copy_object(
        self,
        *,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> dict:
        client = self._client()
        from botocore.exceptions import BotoCoreError, ClientError

        copy_source = {"Bucket": source_bucket, "Key": source_key}
        try:
            client.copy_object(CopySource=copy_source, Bucket=dest_bucket, Key=dest_key)
        except (ClientError, BotoCoreError) as exc:
            log_event(
                "documents.s3.copy.error",
                source_key=source_key,
                dest_key=dest_key,
                detail=str(exc),
            )
            raise RuntimeError(f"S3 copy failed: {exc}") from exc
        return {
            "source_bucket": source_bucket,
            "source_key": source_key,
            "dest_bucket": dest_bucket,
            "dest_key": dest_key,
        }

    def staging_key_for_textract(self, *, source_bucket: str, source_key: str) -> str:
        return f"textract-staging/{source_bucket}/{source_key}"


s3_provider = S3Provider()
