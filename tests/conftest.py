import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.database import make_database
from backend.main import make_app

PASSWORD = "test-only-strong-password-for-fluxosolar"
DATABASES = ["sqlite"] + (["postgresql"] if os.getenv("TEST_DATABASE_URL") else [])


@pytest.fixture(params=DATABASES)
def setup_app(request, tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "rapha")
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    for name in ("REDIS_URL", "S3_BUCKET", "RAILWAY_ENVIRONMENT_ID"):
        monkeypatch.delenv(name, raising=False)
    cleanup = None
    if request.param == "postgresql":
        engine, _ = make_database(os.environ["TEST_DATABASE_URL"])
        schema = "test_fs_" + uuid.uuid4().hex
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = engine.url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
        cleanup = (engine, schema)
    else:
        url = f"sqlite:///{tmp_path / 'growth.db'}"
    app = make_app(url)
    yield app, url
    if cleanup:
        engine, schema = cleanup
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def client(setup_app):
    with TestClient(setup_app[0]) as client:
        yield client


def login(client):
    response = client.post("/api/auth/login", json={"username": "rapha", "password": PASSWORD})
    assert response.status_code == 200
    client.headers["X-FluxoSolar-CSRF"] = "1"
    return response
