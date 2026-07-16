import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config.database.mongo import mongodb
from app.core.config.settings import settings
from app.core.lifespan import lifespan
from app.features.auth.presentation.routes.auth_routes import router as auth_router
from app.features.documents.presentation.routes.document_routes import (
    router as documents_router,
)
from app.features.organizations.presentation.routes.organization_routes import (
    router as organizations_router,
)
from app.shared.exceptions.base import AppException

logger = logging.getLogger("flowops.request")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info("%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error_code": exc.error_code, "message": exc.message},
    )


app.include_router(auth_router)
app.include_router(organizations_router)
app.include_router(documents_router)


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "environment": settings.environment,
        "mongodb": {
            "connected": mongodb.is_connected,
            "database": settings.mongo.database,
        },
    }


@app.get("/config")
async def get_config():
    if settings.is_production:
        return {"error": "Config not available in production"}

    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "debug": settings.debug,
        "mongo": {
            "host": settings.mongo.host,
            "port": settings.mongo.port,
            "database": settings.mongo.database,
        },
        "redis": {
            "host": settings.redis.host,
            "port": settings.redis.port,
        },
        "rabbitmq": {
            "host": settings.rabbitmq.host,
            "port": settings.rabbitmq.port,
        },
        "minio": {
            "host": settings.minio.host,
            "port": settings.minio.port,
            "bucket": settings.minio.bucket,
        },
    }
