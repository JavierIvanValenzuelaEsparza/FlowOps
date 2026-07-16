from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.features.organizations.domain.models import Organization, OrganizationStatus, User, UserRole


class CreateOrganizationDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    plan: str = Field(default="starter")


class UpdateOrganizationDTO(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=100)
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    plan: Optional[str] = None
    max_users: Optional[int] = Field(default=None, gt=0)
    status: Optional[OrganizationStatus] = None


class OrganizationResponseDTO(BaseModel):
    id: str
    name: str
    legal_name: Optional[str]
    tax_id: Optional[str]
    email: EmailStr
    phone: Optional[str]
    address: Optional[str]
    status: OrganizationStatus
    plan: str
    max_users: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, organization: Organization) -> "OrganizationResponseDTO":
        return cls.model_validate(organization.model_dump())


class CreateUserDTO(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8, description="Contraseña en texto plano, mínimo 8 caracteres")
    roles: List[UserRole] = Field(default=[UserRole.VIEWER])


class UserResponseDTO(BaseModel):
    id: str
    organization_id: str
    email: EmailStr
    full_name: str
    roles: List[UserRole]
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> "UserResponseDTO":
        return cls.model_validate(user.model_dump())
