import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config.settings import settings
from app.features.auth.application.dto import TokenResponseDTO
from app.features.organizations.domain.models import User
from app.features.organizations.infrastructure.repositories.organization_repository import (
    OrganizationRepository,
)
from app.shared.exceptions.base import UnauthorizedError

logger = logging.getLogger("flowops.auth")

_password_hasher = PasswordHasher()


class AuthService:
    def __init__(self, repository: OrganizationRepository) -> None:
        self._repository = repository

    @staticmethod
    def _create_token(user: User, token_type: str, expires_minutes: int) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user.id,
            "org": user.organization_id,
            "roles": [role.value for role in user.roles],
            "type": token_type,
            "iat": now,
            "exp": now + timedelta(minutes=expires_minutes),
        }
        return jwt.encode(
            payload,
            settings.security.jwt_secret.get_secret_value(),
            algorithm=settings.security.jwt_algorithm,
        )

    @classmethod
    def create_token_pair(cls, user: User) -> TokenResponseDTO:
        return TokenResponseDTO(
            access_token=cls._create_token(user, "access", settings.security.jwt_expire_minutes),
            refresh_token=cls._create_token(
                user, "refresh", settings.security.jwt_refresh_expire_minutes
            ),
            expires_in=settings.security.jwt_expire_minutes * 60,
        )

    @staticmethod
    def decode_token(token: str, expected_type: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                settings.security.jwt_secret.get_secret_value(),
                algorithms=[settings.security.jwt_algorithm],
            )
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("Token has expired")
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Invalid token")

        if payload.get("type") != expected_type:
            raise UnauthorizedError(f"Expected a {expected_type} token")
        return payload

    async def login(self, email: str, password: str) -> TokenResponseDTO:
        user = await self._repository.get_user_by_email(email)
        if user is None or not user.is_active or not user.password_hash:
            raise UnauthorizedError("Invalid credentials")

        try:
            _password_hasher.verify(user.password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            logger.info("Failed login attempt for %s", email)
            raise UnauthorizedError("Invalid credentials")

        await self._repository.touch_user_login(user.id or "")
        logger.info("User %s logged in", user.id)
        return self.create_token_pair(user)

    async def refresh(self, refresh_token: str) -> TokenResponseDTO:
        payload = self.decode_token(refresh_token, "refresh")
        user = await self._repository.get_user_by_id(payload["sub"])
        if user is None or not user.is_active:
            raise UnauthorizedError("User is no longer active")
        return self.create_token_pair(user)
