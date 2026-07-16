import io
import logging

import urllib3
from minio import Minio

from app.core.config.settings import settings

logger = logging.getLogger("flowops.storage")


class MinIOStorage:
    def __init__(self) -> None:
        self._client = Minio(
            f"{settings.minio.host}:{settings.minio.port}",
            access_key=settings.minio.access_key,
            secret_key=settings.minio.secret_key.get_secret_value(),
            secure=settings.minio.secure,
            http_client=urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=5, read=60),
                retries=urllib3.Retry(total=2, backoff_factor=0.5),
            ),
        )
        self._bucket = settings.minio.bucket

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info("Bucket '%s' created", self._bucket)

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            self._bucket, path, io.BytesIO(data), length=len(data), content_type=content_type
        )
        logger.info("Uploaded '%s' (%d bytes)", path, len(data))

    def download(self, path: str) -> bytes:
        response = self._client.get_object(self._bucket, path)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


minio_storage = MinIOStorage()
