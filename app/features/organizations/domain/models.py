from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, EmailStr


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    APPROVER = "approver"
    VIEWER = "viewer"
    API_INTEGRATION = "api_integration"


class OrganizationStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class Organization(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, description="ID único de la organización")
    name: str = Field(..., min_length=3, max_length=100, description="Nombre de la organización")
    legal_name: Optional[str] = Field(default=None, description="Nombre legal/registrado")
    tax_id: Optional[str] = Field(default=None, description="NIF/CIF/RUT")
    email: EmailStr = Field(..., description="Email de contacto")
    phone: Optional[str] = Field(default=None, description="Teléfono de contacto")
    address: Optional[str] = Field(default=None, description="Dirección física")
    status: OrganizationStatus = Field(default=OrganizationStatus.ACTIVE, description="Estado")
    plan: str = Field(default="starter", description="Plan contratado")
    max_users: int = Field(default=10, description="Máximo de usuarios permitidos")
    created_at: datetime = Field(default_factory=utcnow, description="Fecha de creación")
    updated_at: datetime = Field(default_factory=utcnow, description="Última actualización")


class User(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, description="ID único del usuario")
    organization_id: str = Field(..., description="ID de la organización a la que pertenece")
    email: EmailStr = Field(..., description="Email del usuario")
    full_name: str = Field(..., min_length=2, max_length=100, description="Nombre completo")
    password_hash: Optional[str] = Field(default=None, description="Hash de la contraseña", exclude=True)
    roles: List[UserRole] = Field(default=[UserRole.VIEWER], description="Roles del usuario")
    is_active: bool = Field(default=True, description="Si el usuario está activo")
    last_login_at: Optional[datetime] = Field(default=None, description="Último login")
    created_at: datetime = Field(default_factory=utcnow, description="Fecha de creación")
    updated_at: datetime = Field(default_factory=utcnow, description="Última actualización")
