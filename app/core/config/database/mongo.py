import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config.settings import settings

logger = logging.getLogger("flowops.mongo")


class MongoDB:
    _instance: Optional["MongoDB"] = None
    _client: Optional[AsyncIOMotorClient] = None
    _database: Optional[AsyncIOMotorDatabase] = None

    def __new__(cls) -> "MongoDB":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        if self._client is not None:
            return

        self._client = AsyncIOMotorClient(
            settings.mongo.connection_string_with_replica,
            minPoolSize=settings.mongo.min_pool_size,
            maxPoolSize=settings.mongo.max_pool_size,
            maxIdleTimeMS=settings.mongo.max_idle_time_ms,
            serverSelectionTimeoutMS=settings.mongo.server_selection_timeout_ms,
        )
        self._database = self._client[settings.mongo.database]

        await self._client.admin.command("ping")
        logger.info("Connected to MongoDB database=%s", settings.mongo.database)

    async def disconnect(self) -> None:
        if self._client is None:
            return
        self._client.close()
        self._client = None
        self._database = None
        logger.info("Disconnected from MongoDB")

    @property
    def client(self) -> AsyncIOMotorClient:
        if self._client is None:
            raise RuntimeError("MongoDB is not connected. Call connect() first.")
        return self._client

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            raise RuntimeError("MongoDB is not connected. Call connect() first.")
        return self._database

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._database is not None


mongodb = MongoDB()
