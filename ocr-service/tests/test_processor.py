import asyncio
import hashlib
import json

from src.services.processor import DocumentProcessor


class FakeMinIO:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.uploaded: dict[str, bytes] = {}

    def download(self, path: str) -> bytes:
        return self.files[path]

    def upload(self, path: str, data: bytes, content_type: str = "application/json") -> None:
        self.uploaded[path] = data


class FakeCache:
    def __init__(self) -> None:
        self.store: dict[str, dict] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: dict, ttl=None) -> None:
        self.store[key] = value


class FakeEngine:
    def __init__(self) -> None:
        self.calls = 0

    def process_image(self, image_bytes: bytes) -> dict:
        self.calls += 1
        return {"text": "hola mundo", "confidence": 95.5, "pages": 1}

    def process_pdf(self, pdf_bytes: bytes) -> dict:
        self.calls += 1
        return {"text": "pdf text", "confidence": 90.0, "pages": 2}


def test_process_image_cache_miss_then_hit():
    content = b"fake-image-bytes"
    file_hash = hashlib.sha256(content).hexdigest()
    minio = FakeMinIO({"docs/factura.png": content})
    cache = FakeCache()
    engine = FakeEngine()
    processor = DocumentProcessor(minio, cache, engine)

    job = {"job_id": "job-1", "file_path": "docs/factura.png"}
    result = asyncio.run(processor.process(job))

    assert result["status"] == "completed"
    assert result["file_hash"] == file_hash
    assert result["pages"] == 1
    assert result["confidence"] == 95.5
    assert engine.calls == 1

    result_path = f"ocr-results/{file_hash}.json"
    assert result["result_path"] == result_path
    stored = json.loads(minio.uploaded[result_path])
    assert stored["text"] == "hola mundo"
    assert cache.store[f"ocr:{file_hash}"]["text"] == "hola mundo"

    second = asyncio.run(processor.process({"job_id": "job-2", "file_path": "docs/factura.png"}))
    assert second["status"] == "completed"
    assert engine.calls == 1


def test_process_pdf_detected_by_magic_bytes():
    content = b"%PDF-1.7 fake pdf body"
    minio = FakeMinIO({"docs/contrato.pdf": content})
    processor = DocumentProcessor(minio, FakeCache(), FakeEngine())

    result = asyncio.run(processor.process({"job_id": "job-3", "file_path": "docs/contrato.pdf"}))

    assert result["pages"] == 2
    assert result["confidence"] == 90.0


def test_process_respects_custom_output_path():
    content = b"fake-image"
    minio = FakeMinIO({"in.png": content})
    processor = DocumentProcessor(minio, FakeCache(), FakeEngine())

    result = asyncio.run(processor.process({
        "job_id": "job-4",
        "file_path": "in.png",
        "output_path": "results/custom.json",
    }))

    assert result["result_path"] == "results/custom.json"
    assert "results/custom.json" in minio.uploaded
