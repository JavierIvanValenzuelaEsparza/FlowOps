import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from app.core.config.settings import settings

logger = logging.getLogger("flowops.queue")


class OCRJobPublisher:
    def __init__(self) -> None:
        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._lock = asyncio.Lock()

    async def _ensure_channel(self) -> AbstractChannel:
        async with self._lock:
            if self._channel is None or self._channel.is_closed:
                self._connection = await aio_pika.connect_robust(
                    settings.rabbitmq.connection_string, timeout=10
                )
                self._channel = await self._connection.channel()
                await self._channel.declare_queue(settings.rabbitmq.queue, durable=True)
                logger.info("Publisher connected to RabbitMQ queue '%s'", settings.rabbitmq.queue)
            return self._channel

    async def publish_job(self, job: dict[str, Any]) -> None:
        channel = await self._ensure_channel()
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(job, ensure_ascii=False).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=settings.rabbitmq.queue,
        )
        logger.info("Published OCR job %s", job.get("job_id"))

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._channel = None


class OCRResultConsumer:
    def __init__(self, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self._handler = handler
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="ocr-result-consumer")
            logger.info("OCR result consumer task started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("OCR result consumer stopped")

    async def _run(self) -> None:
        while True:
            try:
                connection = await aio_pika.connect_robust(
                    settings.rabbitmq.connection_string, timeout=10
                )
                async with connection:
                    channel = await connection.channel()
                    await channel.set_qos(prefetch_count=10)
                    queue = await channel.declare_queue(
                        settings.rabbitmq.result_queue, durable=True
                    )
                    logger.info(
                        "Consuming OCR results from '%s'", settings.rabbitmq.result_queue
                    )
                    async with queue.iterator() as iterator:
                        async for message in iterator:
                            async with message.process(requeue=False):
                                await self._on_message(message.body)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("OCR result consumer error (%s); retrying in 5s", exc)
                await asyncio.sleep(5)

    async def _on_message(self, body: bytes) -> None:
        try:
            result = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Discarding malformed OCR result: %r", body[:200])
            return
        try:
            await self._handler(result)
        except Exception:
            logger.exception("Failed to apply OCR result %s", result.get("job_id"))


ocr_job_publisher = OCRJobPublisher()
