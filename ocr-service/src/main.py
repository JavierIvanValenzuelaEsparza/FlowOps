import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.clients.minio import MinIOClient
from src.clients.redis import RedisCache
from src.core.config import settings
from src.services.consumer import RabbitMQConsumer
from src.services.ocr import OCREngine
from src.services.processor import DocumentProcessor

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("pika").setLevel(logging.CRITICAL)
logger = logging.getLogger("ocr.main")

minio_client = MinIOClient()
redis_cache = RedisCache()
ocr_engine = OCREngine()
processor = DocumentProcessor(minio_client, redis_cache, ocr_engine)
consumer = RabbitMQConsumer(processor)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        minio_client.ensure_bucket()
    except Exception as exc:
        logger.warning("Could not verify MinIO bucket at startup: %s", exc)

    consumer.start()
    logger.info("%s started (queue=%s)", settings.SERVICE_NAME, settings.RABBITMQ_QUEUE)

    yield

    consumer.stop()
    await redis_cache.close()
    logger.info("%s stopped", settings.SERVICE_NAME)


app = FastAPI(title="FlowOps OCR Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "consumer_running": consumer.is_running,
        "queue": settings.RABBITMQ_QUEUE,
        "result_queue": settings.RABBITMQ_RESULT_QUEUE,
        "ocr_language": settings.OCR_LANGUAGE,
    }
