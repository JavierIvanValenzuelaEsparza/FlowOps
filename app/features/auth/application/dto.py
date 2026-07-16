from typing import List

from pydantic import BaseModel, EmailStr, Field

from app.features.organizations.domain.models import UserRole


class LoginRequestDTO(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class RefreshRequestDTO(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponseDTO(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUserDTO(BaseModel):
    id: str
    organization_id: str
    email: EmailStr
    full_name: str
    roles: List[UserRole]
