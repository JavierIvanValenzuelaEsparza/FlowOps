import os

os.environ.setdefault("JWT_SECRET", "test-secret-key-with-at-least-32-characters")

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.features.organizations.presentation.routes.organization_routes import get_db
from app.main import app


@pytest.fixture
def mock_db():
    client = AsyncMongoMockClient()
    return client["flowops_test"]


@pytest.fixture
async def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
