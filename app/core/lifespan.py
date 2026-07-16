import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.core.cache.redis import redis_client
from app.core.config.database.mongo import mongodb
from app.core.config.settings import settings
from app.features.documents.application.services import DocumentService
from app.features.documents.infrastructure.queue import OCRResultConsumer, ocr_job_publisher
from app.features.documents.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from app.features.documents.infrastructure.storage import minio_storage
from app.features.organizations.infrastructure.repositories.organization_repository import (
    OrganizationRepository,
)

logger = logging.getLogger("flowops.lifespan")


def _configure_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if settings.logging.file:
        log_path = Path(settings.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))

    logging.basicConfig(
        level=settings.logging.level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


async def _handle_ocr_result(result: dict) -> None:
    service = DocumentService(
        DocumentRepository(mongodb.db), minio_storage, ocr_job_publisher
    )
    await service.apply_ocr_result(result)


ocr_result_consumer = OCRResultConsumer(_handle_ocr_result)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()

    await mongodb.connect()
    await OrganizationRepository(mongodb.db).ensure_indexes()
    await DocumentRepository(mongodb.db).ensure_indexes()

    redis_client.connect()
    ocr_result_consumer.start()
    logger.info("%s v%s started in %s mode", settings.app_name, settings.app_version, settings.environment)

    yield

    await ocr_result_consumer.stop()
    await ocr_job_publisher.close()
    await redis_client.close()
    await mongodb.disconnect()
    logger.info("%s stopped", settings.app_name)
