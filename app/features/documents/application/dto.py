from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

from app.features.documents.domain.models import Document, DocumentStatus

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: Optional[str] = None
    limit: int = Field(ge=1)


class DocumentResponseDTO(BaseModel):
    id: str
    organization_id: str
    uploaded_by: str
    file_name: str
    file_path: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    ocr_text: Optional[str]
    ocr_confidence: Optional[float]
    ocr_pages: Optional[int]
    ocr_result_path: Optional[str]
    file_hash: Optional[str]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, document: Document) -> "DocumentResponseDTO":
        return cls.model_validate(document.model_dump())


class DocumentSummaryDTO(BaseModel):
    id: str
    file_name: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    ocr_confidence: Optional[float]
    ocr_pages: Optional[int]
    created_at: datetime

    @classmethod
    def from_domain(cls, document: Document) -> "DocumentSummaryDTO":
        return cls.model_validate(document.model_dump())
