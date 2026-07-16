import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.core.config.database.mongo import mongodb
from app.core.config.settings import settings
from app.features.organizations.infrastructure.repositories.organization_repository import (
    OrganizationRepository,
)

logger = logging.getLogger("flowops.lifespan")


def _configure_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if settings.logging.file:
        log_path = Path(settings.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))

    logging.basicConfig(
        level=settings.logging.level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()

    await mongodb.connect()
    await OrganizationRepository(mongodb.db).ensure_indexes()
    logger.info("%s v%s started in %s mode", settings.app_name, settings.app_version, settings.environment)

    yield

    await mongodb.disconnect()
    logger.info("%s stopped", settings.app_name)
