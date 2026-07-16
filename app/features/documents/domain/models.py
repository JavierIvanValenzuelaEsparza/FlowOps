from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.features.organizations.domain.models import utcnow


class DocumentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, description="ID único del documento")
    organization_id: str = Field(..., description="Organización propietaria")
    uploaded_by: str = Field(..., description="ID del usuario que subió el documento")
    file_name: str = Field(..., description="Nombre original del archivo")
    file_path: str = Field(..., description="Ruta del archivo en MinIO")
    content_type: str = Field(..., description="MIME type del archivo")
    size_bytes: int = Field(..., ge=0, description="Tamaño en bytes")
    status: DocumentStatus = Field(default=DocumentStatus.PENDING, description="Estado del OCR")
    ocr_text: Optional[str] = Field(default=None, description="Texto extraído por OCR")
    ocr_confidence: Optional[float] = Field(default=None, description="Confianza promedio del OCR")
    ocr_pages: Optional[int] = Field(default=None, description="Páginas procesadas")
    ocr_result_path: Optional[str] = Field(default=None, description="Ruta del JSON de resultado en MinIO")
    file_hash: Optional[str] = Field(default=None, description="SHA-256 del archivo")
    error: Optional[str] = Field(default=None, description="Detalle del error si el OCR falló")
    created_at: datetime = Field(default_factory=utcnow, description="Fecha de creación")
    updated_at: datetime = Field(default_factory=utcnow, description="Última actualización")
