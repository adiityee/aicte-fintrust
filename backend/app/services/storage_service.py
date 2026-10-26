from datetime import datetime, timedelta, timezone
import io
import os
from typing import Optional
from minio import Minio
from minio.error import S3Error
from minio.sse import SseS3

from app.core.config import settings


class StorageService:
    """
    MinIO Object Storage Service
    Provides secure, server-side encrypted (AES-256) storage for FDR documents
    and generates time-limited presigned URLs (<= 5 mins).
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: Optional[bool] = None,
        bucket_name: Optional[str] = None,
    ):
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.access_key = access_key or settings.MINIO_ROOT_USER
        self.secret_key = secret_key or settings.MINIO_ROOT_PASSWORD
        self.secure = secure if secure is not None else settings.MINIO_SECURE
        self.bucket_name = bucket_name or settings.MINIO_BUCKET_FDR

        self._client: Optional[Minio] = None

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        return self._client

    def ensure_bucket_exists(self, bucket_name: Optional[str] = None) -> None:
        """
        Idempotently verifies bucket existence and creates it if absent.
        """
        target_bucket = bucket_name or self.bucket_name
        try:
            if not self.client.bucket_exists(target_bucket):
                self.client.make_bucket(target_bucket)
        except Exception as exc:
            # Re-raise or log appropriately
            raise RuntimeError(f"Failed to ensure MinIO bucket '{target_bucket}': {exc}") from exc

    def upload_fdr_document(
        self,
        fdr_id: str | int,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/pdf",
    ) -> str:
        """
        Uploads an FDR document with AES-256 Server-Side Encryption (SSE-S3).
        Guarantees version immutability by timestamping object keys.
        Returns the unique object key.
        """
        self.ensure_bucket_exists()

        timestamp = int(datetime.now(timezone.utc).timestamp())
        clean_name = os.path.basename(filename).replace(" ", "_")
        object_key = f"fdrs/{fdr_id}/{timestamp}_{clean_name}"

        # Enforce server-side AES-256 encryption
        sse = SseS3()

        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                data=io.BytesIO(file_bytes),
                length=len(file_bytes),
                content_type=content_type,
                sse=sse,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to upload FDR document '{filename}' to MinIO: {exc}") from exc

        return object_key

    def generate_presigned_url(
        self,
        object_key: str,
        expires_in_seconds: int = 300,
    ) -> str:
        """
        Generates a secure, temporary pre-signed download URL valid for under 5 minutes (default: 300s).
        """
        # Ensure requested expiry is under or equal to 300 seconds (5 minutes)
        if expires_in_seconds > 300:
            expires_in_seconds = 300

        bucket = self.bucket_name
        object_name = object_key

        # Strip bucket prefix if passed as 'bucket_name/object_key'
        if object_key.startswith(f"{bucket}/"):
            object_name = object_key[len(bucket) + 1 :]

        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=timedelta(seconds=expires_in_seconds),
            )
            return url
        except Exception as exc:
            raise RuntimeError(f"Failed to generate presigned URL for '{object_key}': {exc}") from exc


# Global service instance
storage_service = StorageService()
