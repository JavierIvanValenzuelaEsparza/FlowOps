import asyncio
import json
import logging
import threading
import time
from typing import Any

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPError
from pika.spec import Basic

from src.core.config import settings
from src.services.processor import DocumentProcessor

logger = logging.getLogger("ocr.consumer")


class RabbitMQConsumer:
    def __init__(self, processor: DocumentProcessor) -> None:
        self._processor = processor
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.is_running = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="ocr-consumer", daemon=True)
        self._thread.start()
        logger.info("Consumer thread started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=15)
        logger.info("Consumer thread stopped")

    def _connect(self) -> pika.BlockingConnection:
        credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
        parameters = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            credentials=credentials,
            heartbeat=settings.RABBITMQ_HEARTBEAT,
            blocked_connection_timeout=300,
            connection_attempts=1,
        )
        return pika.BlockingConnection(parameters)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        while not self._stop_event.is_set():
            try:
                connection = self._connect()
                channel = connection.channel()
                channel.queue_declare(queue=settings.RABBITMQ_QUEUE, durable=True)
                channel.queue_declare(queue=settings.RABBITMQ_RESULT_QUEUE, durable=True)
                channel.basic_qos(prefetch_count=settings.RABBITMQ_PREFETCH)

                self.is_running = True
                logger.info(
                    "Connected to RabbitMQ %s:%d, consuming '%s'",
                    settings.RABBITMQ_HOST, settings.RABBITMQ_PORT, settings.RABBITMQ_QUEUE,
                )

                for method, properties, body in channel.consume(
                    settings.RABBITMQ_QUEUE, inactivity_timeout=1
                ):
                    if self._stop_event.is_set():
                        break
                    if method is None:
                        continue
                    self._handle_message(channel, method, body)

                channel.cancel()
                connection.close()
                self.is_running = False
            except AMQPError as exc:
                self.is_running = False
                logger.warning(
                    "RabbitMQ unavailable (%s); retrying in %ds",
                    exc, settings.RABBITMQ_RECONNECT_DELAY,
                )
                self._stop_event.wait(settings.RABBITMQ_RECONNECT_DELAY)

        self._loop.close()

    def _handle_message(
        self, channel: BlockingChannel, method: Basic.Deliver, body: bytes
    ) -> None:
        try:
            job = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Discarding malformed message: %r", body[:200])
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        job_id = job.get("job_id")
        if not job_id or not job.get("file_path"):
            logger.error("Discarding job without job_id/file_path: %r", job)
            self._publish(channel, {
                "job_id": job_id or "unknown",
                "status": "failed",
                "error": "Job must include 'job_id' and 'file_path'",
            })
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        assert self._loop is not None
        last_error: Exception | None = None
        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                logger.info("[%s] Attempt %d/%d", job_id, attempt, settings.MAX_RETRIES)
                result = self._loop.run_until_complete(self._processor.process(job))
                self._publish(channel, result)
                channel.basic_ack(delivery_tag=method.delivery_tag)
                logger.info("[%s] Job completed", job_id)
                return
            except Exception as exc:
                last_error = exc
                logger.exception("[%s] Attempt %d/%d failed", job_id, attempt, settings.MAX_RETRIES)
                if attempt < settings.MAX_RETRIES:
                    time.sleep(2 ** attempt)

        self._publish(channel, {
            "job_id": job_id,
            "status": "failed",
            "file_path": job.get("file_path"),
            "error": str(last_error),
        })
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        logger.error("[%s] Job failed after %d attempts", job_id, settings.MAX_RETRIES)

    def _publish(self, channel: BlockingChannel, message: dict[str, Any]) -> None:
        channel.basic_publish(
            exchange="",
            routing_key=settings.RABBITMQ_RESULT_QUEUE,
            body=json.dumps(message, ensure_ascii=False).encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                content_type="application/json",
            ),
        )
