import asyncio
import json
import logging
from typing import Any, List, Optional, Tuple
from uuid import uuid4

from app.features.documents.domain.models import Document, DocumentStatus
from app.features.documents.infrastructure.queue import OCRJobPublisher
from app.features.documents.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from app.features.documents.infrastructure.storage import MinIOStorage
from app.features.organizations.domain.models import User, utcnow
from app.shared.exceptions.base import (
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)

logger = logging.getLogger("flowops.documents")

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
}


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        storage: MinIOStorage,
        publisher: OCRJobPublisher,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._publisher = publisher

    async def upload(
        self, user: User, file_name: str, content_type: str, data: bytes
    ) -> Document:
        if content_type not in ALLOWED_CONTENT_TYPES:
            allowed = ", ".join(sorted(ALLOWED_CONTENT_TYPES))
            raise ValidationError(f"Content type '{content_type}' not allowed; use one of: {allowed}")
        if not data:
            raise ValidationError("The uploaded file is empty")

        file_path = f"documents/{user.organization_id}/{uuid4().hex}/{file_name}"
        try:
            await asyncio.to_thread(self._storage.upload, file_path, data, content_type)
        except Exception as exc:
            logger.error("MinIO upload failed for '%s': %s", file_path, exc)
            raise ServiceUnavailableError("Document storage is unavailable, try again later")

        document = Document(
            organization_id=user.organization_id,
            uploaded_by=user.id or "",
            file_name=file_name,
            file_path=file_path,
            content_type=content_type,
            size_bytes=len(data),
        )
        inserted_id = await self._repository.insert_one(document.model_dump(exclude={"id"}))
        document = document.model_copy(update={"id": inserted_id})

        try:
            await self._publisher.publish_job({"job_id": inserted_id, "file_path": file_path})
        except Exception as exc:
            logger.error("Could not enqueue OCR job for %s: %s", inserted_id, exc)
            await self._repository.update_one(
                inserted_id,
                {
                    "status": DocumentStatus.FAILED,
                    "error": "Could not enqueue OCR job",
                    "updated_at": utcnow(),
                },
            )
            raise ServiceUnavailableError("OCR queue is unavailable, try again later")

        logger.info("Document %s uploaded and queued for OCR", inserted_id)
        return document

    async def get_document(self, document_id: str, organization_id: str) -> Document:
        document = await self._repository.find_for_organization(document_id, organization_id)
        if document is None:
            raise NotFoundError(f"Document '{document_id}' not found")
        return document

    async def list_documents(
        self,
        organization_id: str,
        *,
        cursor: Optional[str] = None,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[Document], Optional[str]]:
        return await self._repository.list_by_cursor(
            organization_id, cursor=cursor, limit=limit, status=status
        )

    async def apply_ocr_result(self, result: dict[str, Any]) -> None:
        document_id = result.get("job_id")
        if not document_id:
            logger.warning("OCR result without job_id: %r", result)
            return

        document = await self._repository.find_by_id(document_id)
        if document is None:
            logger.warning("OCR result for unknown document %s", document_id)
            return

        if result.get("status") != "completed":
            await self._repository.update_one(
                document_id,
                {
                    "status": DocumentStatus.FAILED,
                    "error": result.get("error") or "OCR failed",
                    "updated_at": utcnow(),
                },
            )
            logger.info("Document %s marked as failed", document_id)
            return

        update: dict[str, Any] = {
            "status": DocumentStatus.COMPLETED,
            "ocr_confidence": result.get("confidence"),
            "ocr_pages": result.get("pages"),
            "ocr_result_path": result.get("result_path"),
            "file_hash": result.get("file_hash"),
            "error": None,
            "updated_at": utcnow(),
        }

        result_path = result.get("result_path")
        if result_path:
            try:
                payload = await asyncio.to_thread(self._storage.download, result_path)
                update["ocr_text"] = json.loads(payload).get("text")
            except Exception as exc:
                logger.warning(
                    "Could not fetch OCR payload '%s' for %s: %s", result_path, document_id, exc
                )

        await self._repository.update_one(document_id, update)
        logger.info("Document %s completed (pages=%s)", document_id, result.get("pages"))
