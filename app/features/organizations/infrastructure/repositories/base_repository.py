from typing import Any, Generic, List, Optional, Type, TypeVar

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseRepository(Generic[ModelT]):
    collection_name: str
    model: Type[ModelT]

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection: AsyncIOMotorCollection = db[self.collection_name]

    def _to_model(self, document: dict) -> ModelT:
        document = dict(document)
        document["id"] = str(document.pop("_id"))
        return self.model.model_validate(document)

    async def find_by_id(
        self, id: str, *, projection: Optional[dict[str, Any]] = None
    ) -> Optional[ModelT]:
        if not ObjectId.is_valid(id):
            return None
        document = await self.collection.find_one({"_id": ObjectId(id)}, projection)
        return self._to_model(document) if document else None

    async def find_one(
        self, query: dict[str, Any], *, projection: Optional[dict[str, Any]] = None
    ) -> Optional[ModelT]:
        document = await self.collection.find_one(query, projection)
        return self._to_model(document) if document else None

    async def find_many(
        self,
        query: dict[str, Any],
        *,
        skip: int = 0,
        limit: int = 20,
        projection: Optional[dict[str, Any]] = None,
        sort: Optional[list[tuple[str, int]]] = None,
    ) -> List[ModelT]:
        cursor = self.collection.find(query, projection, batch_size=min(limit, 200) or 200)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(limit)
        return [self._to_model(document) async for document in cursor]

    async def count(self, query: dict[str, Any]) -> int:
        return await self.collection.count_documents(query)

    async def insert_one(self, document: dict[str, Any]) -> str:
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)

    async def update_one(self, id: str, update: dict[str, Any]) -> bool:
        if not ObjectId.is_valid(id) or not update:
            return False
        result = await self.collection.update_one({"_id": ObjectId(id)}, {"$set": update})
        return result.matched_count > 0

    async def delete_one(self, query_or_id: dict[str, Any] | str) -> bool:
        query = query_or_id if isinstance(query_or_id, dict) else {"_id": ObjectId(query_or_id)}
        if "_id" in query and not isinstance(query["_id"], ObjectId):
            if not ObjectId.is_valid(query["_id"]):
                return False
            query["_id"] = ObjectId(query["_id"])
        result = await self.collection.delete_one(query)
        return result.deleted_count > 0
