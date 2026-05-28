from __future__ import annotations


class S3Provider:
    def put_object(self, *, object_key: str, raw_bytes: bytes, content_type: str) -> dict:
        # Placeholder adapter to keep S3 migration path explicit.
        return {
            "object_key": object_key,
            "content_type": content_type,
            "size": len(raw_bytes),
            "provider": "s3_stub",
        }


s3_provider = S3Provider()
