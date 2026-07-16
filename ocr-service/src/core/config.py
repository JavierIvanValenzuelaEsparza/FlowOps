from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    SERVICE_NAME: str = Field(default="flowops-ocr", description="Nombre del servicio")
    SERVER_HOST: str = Field(default="0.0.0.0", description="Host del servidor HTTP")
    SERVER_PORT: int = Field(default=8001, description="Puerto del servidor HTTP")

    RABBITMQ_HOST: str = Field(default="localhost", description="RabbitMQ host")
    RABBITMQ_PORT: int = Field(default=5672, description="RabbitMQ port")
    RABBITMQ_USER: str = Field(default="guest", description="RabbitMQ usuario")
    RABBITMQ_PASSWORD: str = Field(default="guest", description="RabbitMQ contraseña")
    RABBITMQ_VHOST: str = Field(default="/", description="RabbitMQ virtual host")
    RABBITMQ_QUEUE: str = Field(default="ocr_jobs", description="Cola de trabajos de OCR")
    RABBITMQ_RESULT_QUEUE: str = Field(default="ocr_results", description="Cola de resultados")
    RABBITMQ_PREFETCH: int = Field(default=1, description="Mensajes sin ack simultáneos por consumidor")
    RABBITMQ_HEARTBEAT: int = Field(default=600, description="Heartbeat AMQP en segundos (alto porque el OCR bloquea)")
    RABBITMQ_RECONNECT_DELAY: int = Field(default=5, description="Segundos entre reintentos de conexión")

    MINIO_HOST: str = Field(default="localhost", description="MinIO host")
    MINIO_PORT: int = Field(default=9000, description="MinIO port")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin", description="MinIO access key")
    MINIO_SECRET_KEY: str = Field(default="minioadmin", description="MinIO secret key")
    MINIO_BUCKET: str = Field(default="flowops-documents", description="Bucket de documentos")
    MINIO_SECURE: bool = Field(default=False, description="Usar HTTPS contra MinIO")

    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_DB: int = Field(default=0, description="Redis database")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis contraseña")
    CACHE_TTL_SECONDS: int = Field(default=86_400, description="TTL del cache de resultados OCR")

    OCR_LANGUAGE: str = Field(default="spa+eng", description="Idiomas de Tesseract")
    OCR_DPI: int = Field(default=200, description="DPI al rasterizar PDFs")
    MAX_RETRIES: int = Field(default=3, description="Reintentos por trabajo antes de marcarlo fallido")

    LOG_LEVEL: str = Field(default="INFO", description="Nivel de logging")

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}")
        return v.upper()

    @property
    def minio_endpoint(self) -> str:
        return f"{self.MINIO_HOST}:{self.MINIO_PORT}"


settings = Settings()
