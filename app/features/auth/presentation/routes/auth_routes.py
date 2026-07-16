from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config.database.deps import get_db
from app.features.auth.application.dto import (
    CurrentUserDTO,
    LoginRequestDTO,
    RefreshRequestDTO,
    TokenResponseDTO,
)
from app.features.auth.application.services import AuthService
from app.features.auth.presentation.dependencies import get_current_user
from app.features.organizations.domain.models import User
from app.features.organizations.infrastructure.repositories.organization_repository import (
    OrganizationRepository,
)
from app.shared.utils.rate_limit import rate_limiter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

login_rate_limit = rate_limiter("login", limit=10, window_seconds=60)


def get_auth_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> AuthService:
    return AuthService(OrganizationRepository(db))


@router.post("/login", response_model=TokenResponseDTO, dependencies=[Depends(login_rate_limit)])
async def login(
    payload: LoginRequestDTO,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponseDTO:
    return await service.login(payload.email, payload.password)


@router.post("/refresh", response_model=TokenResponseDTO)
async def refresh(
    payload: RefreshRequestDTO,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponseDTO:
    return await service.refresh(payload.refresh_token)


@router.get("/me", response_model=CurrentUserDTO)
async def me(user: User = Depends(get_current_user)) -> CurrentUserDTO:
    return CurrentUserDTO(
        id=user.id or "",
        organization_id=user.organization_id,
        email=user.email,
        full_name=user.full_name,
        roles=user.roles,
    )
