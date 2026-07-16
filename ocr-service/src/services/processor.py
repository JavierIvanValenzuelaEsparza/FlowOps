import asyncio
import hashlib
import json
import logging
from typing import Any

from src.clients.minio import MinIOClient
from src.clients.redis import RedisCache
from src.services.ocr import OCREngine

logger = logging.getLogger("ocr.processor")

PDF_MAGIC = b"%PDF"


class DocumentProcessor:
    def __init__(self, minio: MinIOClient, cache: RedisCache, engine: OCREngine) -> None:
        self._minio = minio
        self._cache = cache
        self._engine = engine

    async def process(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = job["job_id"]
        file_path = job["file_path"]
        logger.info("[%s] Starting job for '%s'", job_id, file_path)

        data = await asyncio.to_thread(self._minio.download, file_path)

        file_hash = hashlib.sha256(data).hexdigest()
        cache_key = f"ocr:{file_hash}"
        logger.info("[%s] File hash %s", job_id, file_hash[:16])

        result = await self._cache.get(cache_key)
        if result is None:
            if data.startswith(PDF_MAGIC):
                result = await asyncio.to_thread(self._engine.process_pdf, data)
            else:
                result = await asyncio.to_thread(self._engine.process_image, data)
            logger.info(
                "[%s] OCR finished: pages=%d confidence=%.1f",
                job_id, result["pages"], result["confidence"],
            )
            await self._cache.set(cache_key, result)
        else:
            logger.info("[%s] Served from cache", job_id)

        result_path = job.get("output_path") or f"ocr-results/{file_hash}.json"
        payload = json.dumps(
            {"job_id": job_id, "file_path": file_path, "file_hash": file_hash, **result},
            ensure_ascii=False,
        ).encode("utf-8")
        await asyncio.to_thread(self._minio.upload, result_path, payload)

        logger.info("[%s] Result stored at '%s'", job_id, result_path)
        return {
            "job_id": job_id,
            "status": "completed",
            "file_path": file_path,
            "file_hash": file_hash,
            "result_path": result_path,
            "pages": result["pages"],
            "confidence": result["confidence"],
        }
