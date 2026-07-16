from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config.database.deps import get_db
from app.features.organizations.application.dto import (
    CreateOrganizationDTO,
    CreateUserDTO,
    OrganizationResponseDTO,
    UpdateOrganizationDTO,
    UserResponseDTO,
)
from app.features.organizations.application.services import OrganizationService
from app.features.organizations.domain.models import OrganizationStatus
from app.features.organizations.infrastructure.repositories.organization_repository import (
    OrganizationRepository,
)
from app.shared.dto.response import APIResponse, PaginatedResponse

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


def get_organization_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> OrganizationService:
    return OrganizationService(OrganizationRepository(db))


@router.post("", response_model=APIResponse[OrganizationResponseDTO], status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: CreateOrganizationDTO,
    service: OrganizationService = Depends(get_organization_service),
) -> APIResponse[OrganizationResponseDTO]:
    organization = await service.create_organization(payload)
    return APIResponse(data=OrganizationResponseDTO.from_domain(organization))


@router.get("", response_model=PaginatedResponse[OrganizationResponseDTO])
async def list_organizations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[OrganizationStatus] = Query(default=None, alias="status"),
    service: OrganizationService = Depends(get_organization_service),
) -> PaginatedResponse[OrganizationResponseDTO]:
    organizations, total = await service.list_organizations(
        page=page, page_size=page_size, status=status_filter
    )
    return PaginatedResponse(
        items=[OrganizationResponseDTO.from_domain(o) for o in organizations],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{organization_id}", response_model=APIResponse[OrganizationResponseDTO])
async def get_organization(
    organization_id: str,
    service: OrganizationService = Depends(get_organization_service),
) -> APIResponse[OrganizationResponseDTO]:
    organization = await service.get_organization(organization_id)
    return APIResponse(data=OrganizationResponseDTO.from_domain(organization))


@router.put("/{organization_id}", response_model=APIResponse[OrganizationResponseDTO])
async def update_organization(
    organization_id: str,
    payload: UpdateOrganizationDTO,
    service: OrganizationService = Depends(get_organization_service),
) -> APIResponse[OrganizationResponseDTO]:
    organization = await service.update_organization(organization_id, payload)
    return APIResponse(data=OrganizationResponseDTO.from_domain(organization))


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    organization_id: str,
    service: OrganizationService = Depends(get_organization_service),
) -> None:
    await service.delete_organization(organization_id)


@router.patch("/{organization_id}/activate", response_model=APIResponse[OrganizationResponseDTO])
async def activate_organization(
    organization_id: str,
    service: OrganizationService = Depends(get_organization_service),
) -> APIResponse[OrganizationResponseDTO]:
    organization = await service.set_status(organization_id, OrganizationStatus.ACTIVE)
    return APIResponse(data=OrganizationResponseDTO.from_domain(organization))


@router.patch("/{organization_id}/deactivate", response_model=APIResponse[OrganizationResponseDTO])
async def deactivate_organization(
    organization_id: str,
    service: OrganizationService = Depends(get_organization_service),
) -> APIResponse[OrganizationResponseDTO]:
    organization = await service.set_status(organization_id, OrganizationStatus.INACTIVE)
    return APIResponse(data=OrganizationResponseDTO.from_domain(organization))


@router.post(
    "/{organization_id}/users",
    response_model=APIResponse[UserResponseDTO],
    status_code=status.HTTP_201_CREATED,
)
async def add_user(
    organization_id: str,
    payload: CreateUserDTO,
    service: OrganizationService = Depends(get_organization_service),
) -> APIResponse[UserResponseDTO]:
    user = await service.add_user(organization_id, payload)
    return APIResponse(data=UserResponseDTO.from_domain(user))


@router.get("/{organization_id}/users", response_model=PaginatedResponse[UserResponseDTO])
async def list_users(
    organization_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: OrganizationService = Depends(get_organization_service),
) -> PaginatedResponse[UserResponseDTO]:
    users, total = await service.list_users(organization_id, page=page, page_size=page_size)
    return PaginatedResponse(
        items=[UserResponseDTO.from_domain(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/{organization_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    organization_id: str,
    user_id: str,
    service: OrganizationService = Depends(get_organization_service),
) -> None:
    await service.remove_user(organization_id, user_id)
