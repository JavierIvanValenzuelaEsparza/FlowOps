import os

os.environ.setdefault("JWT_SECRET", "test-secret-key-with-at-least-32-characters")

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core.config.database.deps import get_db
from app.features.documents.presentation.routes.document_routes import (
    get_publisher,
    get_storage,
)
from app.main import app


class FakeStorage:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        self.files[path] = data

    def download(self, path: str) -> bytes:
        return self.files[path]


class FakePublisher:
    def __init__(self):
        self.jobs: list[dict] = []

    async def publish_job(self, job: dict) -> None:
        self.jobs.append(job)


@pytest.fixture
def mock_db():
    client = AsyncMongoMockClient()
    return client["flowops_test"]


@pytest.fixture
def fake_storage():
    return FakeStorage()


@pytest.fixture
def fake_publisher():
    return FakePublisher()


@pytest.fixture
async def client(mock_db, fake_storage, fake_publisher):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage] = lambda: fake_storage
    app.dependency_overrides[get_publisher] = lambda: fake_publisher
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def create_org_with_user(client, org_name="Acme Corp", org_email="contact@example.com",
                               user_email="jane@example.com", password="supersecret123"):
    response = await client.post(
        "/api/v1/organizations", json={"name": org_name, "email": org_email}
    )
    assert response.status_code == 201
    org = response.json()["data"]

    response = await client.post(
        f"/api/v1/organizations/{org['id']}/users",
        json={"email": user_email, "full_name": "Jane Doe", "password": password},
    )
    assert response.status_code == 201
    user = response.json()["data"]
    return org, user


async def login(client, email="jane@example.com", password="supersecret123"):
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
async def auth_context(client):
    org, user = await create_org_with_user(client)
    tokens = await login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return {"org": org, "user": user, "tokens": tokens, "headers": headers}
