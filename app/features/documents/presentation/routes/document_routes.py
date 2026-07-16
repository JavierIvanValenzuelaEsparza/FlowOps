from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config.settings import settings
from app.core.config.database.deps import get_db
from app.features.auth.presentation.dependencies import get_current_user
from app.features.documents.application.dto import (
    CursorPage,
    DocumentResponseDTO,
    DocumentSummaryDTO,
)
from app.features.documents.application.services import DocumentService
from app.features.documents.domain.models import DocumentStatus
from app.features.documents.infrastructure.queue import OCRJobPublisher, ocr_job_publisher
from app.features.documents.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from app.features.documents.infrastructure.storage import MinIOStorage, minio_storage
from app.features.organizations.domain.models import User
from app.shared.dto.response import APIResponse
from app.shared.exceptions.base import ValidationError

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def get_storage() -> MinIOStorage:
    return minio_storage


def get_publisher() -> OCRJobPublisher:
    return ocr_job_publisher


def get_document_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    storage: MinIOStorage = Depends(get_storage),
    publisher: OCRJobPublisher = Depends(get_publisher),
) -> DocumentService:
    return DocumentService(DocumentRepository(db), storage, publisher)


@router.post("", response_model=APIResponse[DocumentResponseDTO], status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> APIResponse[DocumentResponseDTO]:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise ValidationError(f"File exceeds the {settings.max_upload_mb}MB limit")

    document = await service.upload(
        user,
        file.filename or "document",
        file.content_type or "application/octet-stream",
        bytes(data),
    )
    return APIResponse(data=DocumentResponseDTO.from_domain(document))


@router.get("", response_model=CursorPage[DocumentSummaryDTO])
async def list_documents(
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[DocumentStatus] = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> CursorPage[DocumentSummaryDTO]:
    documents, next_cursor = await service.list_documents(
        user.organization_id, cursor=cursor, limit=limit, status=status_filter
    )
    return CursorPage(
        items=[DocumentSummaryDTO.from_domain(d) for d in documents],
        next_cursor=next_cursor,
        limit=limit,
    )


@router.get("/{document_id}", response_model=APIResponse[DocumentResponseDTO])
async def get_document(
    document_id: str,
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> APIResponse[DocumentResponseDTO]:
    document = await service.get_document(document_id, user.organization_id)
    return APIResponse(data=DocumentResponseDTO.from_domain(document))
