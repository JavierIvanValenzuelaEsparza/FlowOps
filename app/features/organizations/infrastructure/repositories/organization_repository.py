from typing import List, Optional, Tuple

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel

from app.features.organizations.domain.models import Organization, User, utcnow
from app.features.organizations.infrastructure.repositories.base_repository import BaseRepository

USER_LIST_PROJECTION = {"password_hash": 0}


class OrganizationRepository(BaseRepository[Organization]):
    collection_name = "organizations"
    model = Organization

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)
        self.users = db["users"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_indexes(
            [
                IndexModel([("email", ASCENDING)], unique=True, name="uq_organization_email"),
                IndexModel([("name", ASCENDING)], unique=True, name="uq_organization_name"),
            ]
        )
        await self.users.create_indexes(
            [
                IndexModel([("email", ASCENDING)], unique=True, name="uq_user_email"),
                IndexModel([("organization_id", ASCENDING)], name="ix_user_organization_id"),
            ]
        )

    async def get_by_name(self, name: str) -> Optional[Organization]:
        return await self.find_one({"name": name})

    async def list_organizations(
        self, *, skip: int = 0, limit: int = 20, status: Optional[str] = None
    ) -> Tuple[List[Organization], int]:
        query = {"status": status} if status else {}
        items = await self.find_many(query, skip=skip, limit=limit, sort=[("created_at", -1)])
        total = await self.count(query)
        return items, total

    async def add_user(self, organization_id: str, user: User) -> User:
        document = user.model_dump(exclude={"id"})
        document["password_hash"] = user.password_hash
        result = await self.users.insert_one(document)
        return user.model_copy(update={"id": str(result.inserted_id)})

    async def get_user_by_email(self, email: str) -> Optional[User]:
        document = await self.users.find_one({"email": email})
        if document is None:
            return None
        document = dict(document)
        document["id"] = str(document.pop("_id"))
        return User.model_validate(document)

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        if not ObjectId.is_valid(user_id):
            return None
        document = await self.users.find_one({"_id": ObjectId(user_id)})
        if document is None:
            return None
        document = dict(document)
        document["id"] = str(document.pop("_id"))
        return User.model_validate(document)

    async def touch_user_login(self, user_id: str) -> None:
        if not ObjectId.is_valid(user_id):
            return
        await self.users.update_one(
            {"_id": ObjectId(user_id)}, {"$set": {"last_login_at": utcnow()}}
        )

    async def delete_users_by_organization(self, organization_id: str) -> int:
        result = await self.users.delete_many({"organization_id": organization_id})
        return result.deleted_count

    async def list_users(
        self, organization_id: str, *, skip: int = 0, limit: int = 20
    ) -> Tuple[List[User], int]:
        query = {"organization_id": organization_id}
        cursor = self.users.find(query, USER_LIST_PROJECTION, batch_size=min(limit, 200) or 200)
        cursor = cursor.sort([("created_at", -1)]).skip(skip).limit(limit)

        items: List[User] = []
        async for document in cursor:
            document = dict(document)
            document["id"] = str(document.pop("_id"))
            items.append(User.model_validate(document))

        total = await self.users.count_documents(query)
        return items, total

    async def count_users(self, organization_id: str) -> int:
        return await self.users.count_documents({"organization_id": organization_id})

    async def remove_user(self, organization_id: str, user_id: str) -> bool:
        if not ObjectId.is_valid(user_id):
            return False
        result = await self.users.delete_one(
            {"_id": ObjectId(user_id), "organization_id": organization_id}
        )
        return result.deleted_count > 0
