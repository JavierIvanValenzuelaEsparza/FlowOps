async def create_organization(client, name="Acme Corp", email="contact@example.com"):
    response = await client.post(
        "/api/v1/organizations",
        json={"name": name, "email": email},
    )
    assert response.status_code == 201
    return response.json()["data"]


async def test_create_and_get_organization(client):
    organization = await create_organization(client)
    assert organization["name"] == "Acme Corp"
    assert organization["status"] == "active"

    response = await client.get(f"/api/v1/organizations/{organization['id']}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == organization["id"]


async def test_create_organization_duplicate_name_conflicts(client):
    await create_organization(client, name="Acme Corp", email="a@example.com")
    response = await client.post(
        "/api/v1/organizations",
        json={"name": "Acme Corp", "email": "b@example.com"},
    )
    assert response.status_code == 409


async def test_get_missing_organization_returns_404(client):
    response = await client.get("/api/v1/organizations/000000000000000000000000")
    assert response.status_code == 404


async def test_list_organizations_is_paginated(client):
    for i in range(3):
        await create_organization(client, name=f"Org {i}", email=f"org{i}@example.com")

    response = await client.get("/api/v1/organizations", params={"page": 1, "page_size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_update_organization(client):
    organization = await create_organization(client)
    response = await client.put(
        f"/api/v1/organizations/{organization['id']}",
        json={"legal_name": "Acme Corporation LLC"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["legal_name"] == "Acme Corporation LLC"


async def test_delete_organization(client):
    organization = await create_organization(client)
    response = await client.delete(f"/api/v1/organizations/{organization['id']}")
    assert response.status_code == 204

    response = await client.get(f"/api/v1/organizations/{organization['id']}")
    assert response.status_code == 404


async def test_add_list_and_remove_user(client):
    organization = await create_organization(client)
    org_id = organization["id"]

    response = await client.post(
        f"/api/v1/organizations/{org_id}/users",
        json={"email": "user@example.com", "full_name": "Jane Doe", "password": "supersecret"},
    )
    assert response.status_code == 201
    user = response.json()["data"]
    assert "password" not in user
    assert "password_hash" not in user

    response = await client.get(f"/api/v1/organizations/{org_id}/users")
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = await client.delete(f"/api/v1/organizations/{org_id}/users/{user['id']}")
    assert response.status_code == 204

    response = await client.get(f"/api/v1/organizations/{org_id}/users")
    assert response.json()["total"] == 0


async def test_add_user_respects_max_users_limit(client):
    organization = await create_organization(client)
    org_id = organization["id"]
    await client.put(f"/api/v1/organizations/{org_id}", json={"max_users": 1})

    first = await client.post(
        f"/api/v1/organizations/{org_id}/users",
        json={"email": "one@example.com", "full_name": "User One", "password": "supersecret"},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/organizations/{org_id}/users",
        json={"email": "two@example.com", "full_name": "User Two", "password": "supersecret"},
    )
    assert second.status_code == 422
