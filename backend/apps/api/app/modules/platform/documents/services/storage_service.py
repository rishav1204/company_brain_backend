from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings


class StorageService:
    def _cloudinary_ready(self) -> bool:
        return bool(settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret)

    def build_object_key(self, *, org_id: str, document_type: str, file_name: str) -> str:
        now = datetime.now(timezone.utc)
        safe_name = file_name.replace("\\", "_").replace("/", "_").strip() or "document.bin"
        return f"{org_id}/{document_type}/{now:%Y/%m/%d}/{safe_name}"

    def upload(self, *, org_id: str, document_type: str, file_name: str, raw_bytes: bytes, mime_type: str) -> dict:
        object_key = self.build_object_key(org_id=org_id, document_type=document_type, file_name=file_name)
        if not self._cloudinary_ready():
            raise RuntimeError("Cloudinary credentials missing. Set CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET.")
        if not raw_bytes:
            raise ValueError("Upload requires base64_content (raw bytes missing).")

        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=settings.cloudinary_secure,
        )

        folder = f"{settings.documents_bucket_prefix}/{org_id}/{document_type}/{datetime.now(timezone.utc):%Y/%m/%d}"
        safe_public_id = file_name.rsplit(".", 1)[0].replace("\\", "_").replace("/", "_").strip() or "document"
        resource_type = "image" if mime_type.lower().startswith("image/") else "raw"
        upload_result = cloudinary.uploader.upload(
            raw_bytes,
            resource_type=resource_type,
            folder=folder,
            public_id=safe_public_id,
            overwrite=False,
            use_filename=False,
            unique_filename=True,
        )
        public_id = str(upload_result.get("public_id", ""))
        storage_path = f"cloudinary://{settings.cloudinary_cloud_name}/{resource_type}/{public_id}"
        return {
            "storage_path": storage_path,
            "object_key": object_key,
            "provider": "cloudinary",
            "bytes": len(raw_bytes),
            "mime_type": mime_type,
            "cloudinary": {
                "public_id": public_id,
                "resource_type": resource_type,
                "version": upload_result.get("version"),
                "etag": upload_result.get("etag"),
                "secure_url": upload_result.get("secure_url"),
            },
        }

    def signed_download_url(self, storage_path: str, expires_in_seconds: int = 900) -> str:
        if storage_path.startswith("cloudinary://"):
            # cloudinary://<cloud>/<resource_type>/<public_id>
            try:
                _, rest = storage_path.split("cloudinary://", 1)
                parts = rest.split("/", 2)
                if len(parts) != 3:
                    raise ValueError("invalid cloudinary storage_path")
                cloud_name, resource_type, public_id = parts[0], parts[1], parts[2]
            except Exception:
                return storage_path
            if not self._cloudinary_ready():
                return storage_path
            import cloudinary
            from cloudinary.utils import cloudinary_url

            cloudinary.config(
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key,
                api_secret=settings.cloudinary_api_secret,
                secure=settings.cloudinary_secure,
            )
            expires_at = int(datetime.now(timezone.utc).timestamp()) + max(60, int(expires_in_seconds))
            url, _ = cloudinary_url(
                public_id,
                resource_type=resource_type,
                secure=settings.cloudinary_secure,
                sign_url=True,
                expires_at=expires_at,
            )
            return url
        return storage_path

    def preview_urls(self, storage_path: str, *, mime_type: str, expires_in_seconds: int = 900) -> dict:
        """
        Return derived preview URLs for workflow/task UIs.

        For Cloudinary assets:
        - `download_url`: signed original delivery url
        - `thumbnail_url`: small thumbnail (image or first-page PDF render)
        - `preview_url`: larger preview (image or first-page PDF render)
        """
        download_url = self.signed_download_url(storage_path, expires_in_seconds=expires_in_seconds)
        if not storage_path.startswith("cloudinary://") or not self._cloudinary_ready():
            return {"download_url": download_url, "thumbnail_url": None, "preview_url": None}

        try:
            _, rest = storage_path.split("cloudinary://", 1)
            parts = rest.split("/", 2)
            if len(parts) != 3:
                raise ValueError("invalid cloudinary storage_path")
            _, resource_type, public_id = parts[0], parts[1], parts[2]
        except Exception:
            return {"download_url": download_url, "thumbnail_url": None, "preview_url": None}

        import cloudinary
        from cloudinary.utils import cloudinary_url

        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=settings.cloudinary_secure,
        )
        expires_at = int(datetime.now(timezone.utc).timestamp()) + max(60, int(expires_in_seconds))
        mt = (mime_type or "").lower()

        def _signed_url(*, rtype: str, transformation: list[dict]) -> str:
            url, _ = cloudinary_url(
                public_id,
                resource_type=rtype,
                secure=settings.cloudinary_secure,
                sign_url=True,
                expires_at=expires_at,
                transformation=transformation,
            )
            return url

        if mt == "application/pdf":
            # Render first page as image for thumbnail/preview.
            thumb = _signed_url(
                rtype="image",
                transformation=[
                    {"page": 1},
                    {"width": 320, "height": 320, "crop": "fit"},
                    {"fetch_format": "jpg", "quality": "auto"},
                ],
            )
            prev = _signed_url(
                rtype="image",
                transformation=[
                    {"page": 1},
                    {"width": 1200, "height": 1200, "crop": "fit"},
                    {"fetch_format": "jpg", "quality": "auto"},
                ],
            )
            return {"download_url": download_url, "thumbnail_url": thumb, "preview_url": prev}

        if mt.startswith("image/"):
            thumb = _signed_url(
                rtype=resource_type,
                transformation=[
                    {"width": 320, "height": 320, "crop": "fill"},
                    {"fetch_format": "jpg", "quality": "auto"},
                ],
            )
            prev = _signed_url(
                rtype=resource_type,
                transformation=[
                    {"width": 1200, "height": 1200, "crop": "fit"},
                    {"fetch_format": "jpg", "quality": "auto"},
                ],
            )
            return {"download_url": download_url, "thumbnail_url": thumb, "preview_url": prev}

        return {"download_url": download_url, "thumbnail_url": None, "preview_url": None}


storage_service = StorageService()
