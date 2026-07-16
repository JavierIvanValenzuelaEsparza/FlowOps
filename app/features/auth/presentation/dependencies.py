from typing import Awaitable, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config.database.deps import get_db
from app.features.auth.application.services import AuthService
from app.features.organizations.domain.models import User, UserRole
from app.features.organizations.infrastructure.repositories.organization_repository import (
    OrganizationRepository,
)
from app.shared.exceptions.base import ForbiddenError, UnauthorizedError

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")

    payload = AuthService.decode_token(credentials.credentials, "access")
    user = await OrganizationRepository(db).get_user_by_id(payload["sub"])
    if user is None or not user.is_active:
        raise UnauthorizedError("User is no longer active")
    return user


def require_roles(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    async def checker(user: User = Depends(get_current_user)) -> User:
        if not set(roles) & set(user.roles):
            allowed = ", ".join(role.value for role in roles)
            raise ForbiddenError(f"This action requires one of the roles: {allowed}")
        return user

    return checker
