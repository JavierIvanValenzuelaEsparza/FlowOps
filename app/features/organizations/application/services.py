from typing import List, Tuple

from argon2 import PasswordHasher
from argon2.exceptions import HashingError

from app.features.organizations.application.dto import (
    CreateOrganizationDTO,
    CreateUserDTO,
    UpdateOrganizationDTO,
)
from app.features.organizations.domain.models import (
    Organization,
    OrganizationStatus,
    User,
    utcnow,
)
from app.features.organizations.infrastructure.repositories.organization_repository import (
    OrganizationRepository,
)
from app.shared.exceptions.base import ConflictError, NotFoundError, ValidationError

_password_hasher = PasswordHasher()


class OrganizationService:
    def __init__(self, repository: OrganizationRepository) -> None:
        self._repository = repository

    async def create_organization(self, dto: CreateOrganizationDTO) -> Organization:
        if await self._repository.get_by_name(dto.name) is not None:
            raise ConflictError(f"An organization named '{dto.name}' already exists")

        organization = Organization(**dto.model_dump())
        inserted_id = await self._repository.insert_one(
            organization.model_dump(exclude={"id"})
        )
        return organization.model_copy(update={"id": inserted_id})

    async def get_organization(self, organization_id: str) -> Organization:
        organization = await self._repository.find_by_id(organization_id)
        if organization is None:
            raise NotFoundError(f"Organization '{organization_id}' not found")
        return organization

    async def list_organizations(
        self, *, page: int = 1, page_size: int = 20, status: str | None = None
    ) -> Tuple[List[Organization], int]:
        skip = (page - 1) * page_size
        return await self._repository.list_organizations(skip=skip, limit=page_size, status=status)

    async def update_organization(
        self, organization_id: str, dto: UpdateOrganizationDTO
    ) -> Organization:
        await self.get_organization(organization_id)

        update_data = dto.model_dump(exclude_unset=True)
        if "name" in update_data:
            existing = await self._repository.get_by_name(update_data["name"])
            if existing is not None and existing.id != organization_id:
                raise ConflictError(f"An organization named '{update_data['name']}' already exists")

        if update_data:
            update_data["updated_at"] = utcnow()
            await self._repository.update_one(organization_id, update_data)

        return await self.get_organization(organization_id)

    async def delete_organization(self, organization_id: str) -> None:
        await self.get_organization(organization_id)
        await self._repository.delete_one(organization_id)

    async def set_status(self, organization_id: str, status: OrganizationStatus) -> Organization:
        return await self.update_organization(
            organization_id, UpdateOrganizationDTO(status=status)
        )

    async def add_user(self, organization_id: str, dto: CreateUserDTO) -> User:
        organization = await self.get_organization(organization_id)

        if await self._repository.get_user_by_email(dto.email) is not None:
            raise ConflictError(f"A user with email '{dto.email}' already exists")

        current_users = await self._repository.count_users(organization_id)
        if current_users >= organization.max_users:
            raise ValidationError(
                f"Organization '{organization_id}' reached its limit of {organization.max_users} users"
            )

        try:
            password_hash = _password_hasher.hash(dto.password)
        except HashingError as exc:
            raise ValidationError("Could not process the provided password") from exc

        user = User(
            organization_id=organization_id,
            email=dto.email,
            full_name=dto.full_name,
            password_hash=password_hash,
            roles=dto.roles,
        )
        return await self._repository.add_user(organization_id, user)

    async def list_users(
        self, organization_id: str, *, page: int = 1, page_size: int = 20
    ) -> Tuple[List[User], int]:
        await self.get_organization(organization_id)
        skip = (page - 1) * page_size
        return await self._repository.list_users(organization_id, skip=skip, limit=page_size)

    async def remove_user(self, organization_id: str, user_id: str) -> None:
        await self.get_organization(organization_id)
        removed = await self._repository.remove_user(organization_id, user_id)
        if not removed:
            raise NotFoundError(f"User '{user_id}' not found in organization '{organization_id}'")
