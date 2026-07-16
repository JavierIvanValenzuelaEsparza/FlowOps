from tests.conftest import create_org_with_user, login


async def test_login_returns_token_pair(client):
    await create_org_with_user(client)
    tokens = await login(client)
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["expires_in"] > 0


async def test_login_wrong_password_returns_401(client):
    await create_org_with_user(client)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "jane@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "unauthorized"


async def test_login_unknown_user_returns_401(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever123"},
    )
    assert response.status_code == 401


async def test_me_returns_current_user(client, auth_context):
    response = await client.get("/api/v1/auth/me", headers=auth_context["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert body["organization_id"] == auth_context["org"]["id"]


async def test_me_without_token_returns_401(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_garbage_token_returns_401(client):
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401


async def test_refresh_issues_new_pair(client, auth_context):
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_context["tokens"]["refresh_token"]},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_rejects_access_token(client, auth_context):
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_context["tokens"]["access_token"]},
    )
    assert response.status_code == 401
