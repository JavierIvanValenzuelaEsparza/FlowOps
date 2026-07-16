import json

from app.features.documents.application.services import DocumentService
from app.features.documents.infrastructure.repositories.document_repository import (
    DocumentRepository,
)

PDF_BYTES = b"%PDF-1.7 fake pdf content"


async def upload_document(client, headers, file_name="factura.pdf", content=PDF_BYTES):
    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": (file_name, content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_upload_requires_auth(client):
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("x.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 401


async def test_upload_stores_file_and_enqueues_job(client, auth_context, fake_storage, fake_publisher):
    document = await upload_document(client, auth_context["headers"])

    assert document["status"] == "pending"
    assert document["organization_id"] == auth_context["org"]["id"]
    assert document["size_bytes"] == len(PDF_BYTES)
    assert fake_storage.files[document["file_path"]] == PDF_BYTES
    assert fake_publisher.jobs == [
        {"job_id": document["id"], "file_path": document["file_path"]}
    ]


async def test_upload_rejects_disallowed_content_type(client, auth_context):
    response = await client.post(
        "/api/v1/documents",
        headers=auth_context["headers"],
        files={"file": ("run.exe", b"MZ...", "application/x-msdownload")},
    )
    assert response.status_code == 422


async def test_get_document_scoped_to_organization(client, auth_context):
    document = await upload_document(client, auth_context["headers"])

    response = await client.get(
        f"/api/v1/documents/{document['id']}", headers=auth_context["headers"]
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == document["id"]

    response = await client.get(
        "/api/v1/documents/000000000000000000000000", headers=auth_context["headers"]
    )
    assert response.status_code == 404


async def test_list_documents_cursor_pagination(client, auth_context):
    for i in range(3):
        await upload_document(client, auth_context["headers"], file_name=f"doc{i}.pdf")

    response = await client.get(
        "/api/v1/documents", headers=auth_context["headers"], params={"limit": 2}
    )
    assert response.status_code == 200
    page1 = response.json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"] is not None

    response = await client.get(
        "/api/v1/documents",
        headers=auth_context["headers"],
        params={"limit": 2, "cursor": page1["next_cursor"]},
    )
    page2 = response.json()
    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None

    ids = {d["id"] for d in page1["items"]} | {d["id"] for d in page2["items"]}
    assert len(ids) == 3


async def test_apply_ocr_result_persists_text(client, auth_context, mock_db, fake_storage, fake_publisher):
    document = await upload_document(client, auth_context["headers"])

    result_path = "ocr-results/abc123.json"
    fake_storage.files[result_path] = json.dumps(
        {"text": "texto extraído del documento", "confidence": 97.3, "pages": 2}
    ).encode()

    service = DocumentService(DocumentRepository(mock_db), fake_storage, fake_publisher)
    await service.apply_ocr_result({
        "job_id": document["id"],
        "status": "completed",
        "result_path": result_path,
        "file_hash": "abc123",
        "pages": 2,
        "confidence": 97.3,
    })

    response = await client.get(
        f"/api/v1/documents/{document['id']}", headers=auth_context["headers"]
    )
    body = response.json()["data"]
    assert body["status"] == "completed"
    assert body["ocr_text"] == "texto extraído del documento"
    assert body["ocr_pages"] == 2
    assert body["ocr_confidence"] == 97.3


async def test_apply_ocr_result_failure_marks_document_failed(client, auth_context, mock_db, fake_storage, fake_publisher):
    document = await upload_document(client, auth_context["headers"])

    service = DocumentService(DocumentRepository(mock_db), fake_storage, fake_publisher)
    await service.apply_ocr_result({
        "job_id": document["id"],
        "status": "failed",
        "error": "corrupted file",
    })

    response = await client.get(
        f"/api/v1/documents/{document['id']}", headers=auth_context["headers"]
    )
    body = response.json()["data"]
    assert body["status"] == "failed"
    assert body["error"] == "corrupted file"


async def test_list_documents_excludes_text_payload(client, auth_context):
    await upload_document(client, auth_context["headers"])
    response = await client.get("/api/v1/documents", headers=auth_context["headers"])
    items = response.json()["items"]
    assert items and "ocr_text" not in items[0]
