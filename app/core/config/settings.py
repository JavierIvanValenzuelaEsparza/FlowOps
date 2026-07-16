from typing import Optional
from pydantic import Field, field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class MongoSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_prefix="MONGO_", env_file=".env", extra="ignore")

    host: str = Field(default="localhost", description="MongoDB host")
    port: int = Field(default=27017, description="MongoDB port")
    database: str = Field(default="flowops", description="MongoDB database name")
    username: Optional[str] = Field(default=None, description="MongoDB username")
    password: Optional[SecretStr] = Field(default=None, description="MongoDB password")
    replica_set: Optional[str] = Field(default=None, description="MongoDB replica set name")
    min_pool_size: int = Field(default=10, description="Minimum size of the connection pool")
    max_pool_size: int = Field(default=100, description="Maximum size of the connection pool")
    max_idle_time_ms: int = Field(default=30_000, description="Close idle pooled connections after this many ms")
    server_selection_timeout_ms: int = Field(default=5_000, description="Fail fast if no server is reachable")

    @property
    def connection_string(self) -> str:
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.database}"
        return f"mongodb://{self.host}:{self.port}/{self.database}"

    @property
    def connection_string_with_replica(self) -> str:
        base = self.connection_string
        if self.replica_set:
            base += f"?replicaSet={self.replica_set}"
        return base


class RedisSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database number")
    password: Optional[str] = Field(default=None, description="Redis password")

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class RabbitMQSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", env_file=".env", extra="ignore")

    host: str = Field(default="localhost", description="RabbitMQ host")
    port: int = Field(default=5672, description="RabbitMQ port")
    user: str = Field(default="guest", description="RabbitMQ username")
    password: str = Field(default="guest", description="RabbitMQ password")
    vhost: str = Field(default="/", description="RabbitMQ virtual host")

    @property
    def connection_string(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}{self.vhost}"


class MinIOSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_prefix="MINIO_", env_file=".env", extra="ignore")

    host: str = Field(default="localhost", description="MinIO host")
    port: int = Field(default=9000, description="MinIO port")
    access_key: str = Field(default="minioadmin", description="MinIO access key")
    secret_key: SecretStr = Field(default=SecretStr("minioadmin"), description="MinIO secret key")
    bucket: str = Field(default="flowops-documents", description="Default bucket name")
    secure: bool = Field(default=False, description="Use HTTPS")

    @property
    def endpoint(self) -> str:
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.host}:{self.port}"


class SecuritySettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: SecretStr = Field(default=SecretStr("your-secret-key-change-in-production"), description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_expire_minutes: int = Field(default=1440, description="JWT expiration in minutes")

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v


class LoggingSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOG_", env_file=".env", extra="ignore")

    level: str = Field(default="INFO", description="Log level")
    file: Optional[str] = Field(default=None, description="Log file path")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()


class Settings(EnvBaseSettings):
    app_name: str = Field(default="FlowOps API", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(default="development", description="Environment (development/staging/production)")
    debug: bool = Field(default=True, description="Debug mode")

    server_host: str = Field(default="0.0.0.0", description="Server host")
    server_port: int = Field(default=8000, description="Server port")

    mongo: MongoSettings = Field(default_factory=MongoSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


settings = Settings()
