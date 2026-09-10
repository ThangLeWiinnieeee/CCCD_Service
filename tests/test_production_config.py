import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from cccd_service.config import Settings
from cccd_service.main import create_app


def test_production_disables_docs_and_preloads_ocr(monkeypatch):
    calls = []
    monkeypatch.setattr("cccd_service.main.get_ocr_engine", lambda: calls.append(True))
    settings = Settings(
        _env_file=None,
        NODE_ENV="production",
        internal_secret="x" * 32,
    )

    app = create_app(settings)

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert calls == [True]


def test_production_requires_strong_internal_secret():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            _env_file=None,
            NODE_ENV="production",
            internal_secret="too-short",
        )


def test_api_rejects_bad_secret_before_parsing_multipart():
    settings = Settings(
        _env_file=None,
        NODE_ENV="development",
        internal_secret="test-internal-secret",
    )

    with TestClient(create_app(settings)) as client:
        response = client.post("/api/verify")

    assert response.status_code == 401
    assert response.json() == {"detail": "Sai hoặc thiếu internal secret"}
