from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config.database.mongo import mongodb


def get_db() -> AsyncIOMotorDatabase:
    return mongodb.db
