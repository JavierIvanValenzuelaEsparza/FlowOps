from typing import List, Optional, Tuple

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.features.documents.domain.models import Document
from app.features.organizations.infrastructure.repositories.base_repository import BaseRepository

LIST_PROJECTION = {"ocr_text": 0}


class DocumentRepository(BaseRepository[Document]):
    collection_name = "documents"
    model = Document

    async def ensure_indexes(self) -> None:
        await self.collection.create_indexes(
            [
                IndexModel(
                    [("organization_id", ASCENDING), ("_id", DESCENDING)],
                    name="ix_document_org_id",
                ),
                IndexModel([("file_hash", ASCENDING)], name="ix_document_file_hash"),
            ]
        )

    async def list_by_cursor(
        self,
        organization_id: str,
        *,
        cursor: Optional[str] = None,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[Document], Optional[str]]:
        query: dict = {"organization_id": organization_id}
        if status:
            query["status"] = status
        if cursor and ObjectId.is_valid(cursor):
            query["_id"] = {"$lt": ObjectId(cursor)}

        items = await self.find_many(
            query,
            limit=limit + 1,
            projection=LIST_PROJECTION,
            sort=[("_id", -1)],
        )
        next_cursor = None
        if len(items) > limit:
            items = items[:limit]
            next_cursor = items[-1].id
        return items, next_cursor

    async def find_for_organization(
        self, document_id: str, organization_id: str
    ) -> Optional[Document]:
        if not ObjectId.is_valid(document_id):
            return None
        document = await self.collection.find_one(
            {"_id": ObjectId(document_id), "organization_id": organization_id}
        )
        return self._to_model(document) if document else None
