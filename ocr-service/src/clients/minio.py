import io
import logging

import urllib3
from minio import Minio

from src.core.config import settings

logger = logging.getLogger("ocr.minio")


class MinIOClient:
    def __init__(self) -> None:
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            http_client=urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=5, read=60),
                retries=urllib3.Retry(total=2, backoff_factor=0.5),
            ),
        )
        self._bucket = settings.MINIO_BUCKET

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info("Bucket '%s' created", self._bucket)

    def download(self, path: str) -> bytes:
        logger.info("Downloading '%s' from bucket '%s'", path, self._bucket)
        response = self._client.get_object(self._bucket, path)
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()
        logger.info("Downloaded '%s' (%d bytes)", path, len(data))
        return data

    def upload(self, path: str, data: bytes, content_type: str = "application/json") -> None:
        self._client.put_object(
            self._bucket,
            path,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        logger.info("Uploaded '%s' (%d bytes)", path, len(data))
