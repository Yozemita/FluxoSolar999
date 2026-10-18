from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.database import Audit, Owner, Session, now
from backend.main import make_app
from backend.security import COOKIE, verify_password
from tests.conftest import PASSWORD, login


def test_public_health_dashboard_and_protected_data(client):
    assert client.get("/health").json()["database"] == "ready"
    html = client.get("/")
    assert html.status_code == 200 and "Creative Studio" in html.text
    for asset in ("app.js", "style.css"):
        assert client.get("/static/" + asset).status_code == 200
    assert "script-src 'self'" in html.headers["Content-Security-Policy"]
    assert client.get("/openapi.json").status_code == 200
    for route in ("/api/products", "/products", "/winners", "/agents", "/api/dashboard", "/api/creatives", "/api/schedules", "/api/agent-runs", "/api/status"):
        assert client.get(route).status_code == 401


def test_auth_hash_csrf_expiry_and_logout(client):
    assert client.post("/api/auth/login", json={"username": "rapha", "password": "wrong"}).status_code == 401
    response = login(client)
    assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=strict" in response.headers["set-cookie"]
    token = client.cookies[COOKIE]
    with client.app.state.sessions() as db:
        user = db.scalar(select(Owner))
        session = db.scalar(select(Session))
        assert verify_password(PASSWORD, user.password_hash) and PASSWORD not in user.password_hash
        assert token != session.digest and len(session.digest) == 64
    del client.headers["X-FluxoSolar-CSRF"]
    assert client.post("/api/creatives", json={"product_id": 1}).status_code == 403
    client.headers["X-FluxoSolar-CSRF"] = "1"
    assert client.get("/api/auth/me").json()["username"] == "rapha"
    assert client.post("/api/auth/logout", json={}).status_code == 200
    client.cookies.set(COOKIE, token)
    assert client.get("/api/products").status_code == 401
    login(client)
    with client.app.state.sessions() as db:
        for session in db.scalars(select(Session)):
            session.expires = now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/products").status_code == 401


def test_rate_limit_origin_and_secure_cookie(client, monkeypatch):
    assert client.post("/api/auth/login", headers={"Origin": "https://evil.example"}, json={"username": "rapha", "password": PASSWORD}).status_code == 403
    monkeypatch.setenv("COOKIE_SECURE", "true")
    response = login(client)
    assert "; Secure" in response.headers["set-cookie"]
    for _ in range(9):
        assert client.post("/api/auth/login", json={"username": "rapha", "password": "bad"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "rapha", "password": PASSWORD}).status_code == 429


def test_catalog_preserves_query_and_rejects_wrong_merchant(client):
    login(client)
    product = {"merchant": "SHOPEE", "external_code": "TEST-SKU", "title": "Produto verificado", "affiliate_url": "https://br.shp.ee/example?affiliate=keep%2Bthis&x=a%20b"}
    response = client.post("/api/products", json=product)
    assert response.status_code == 201 and response.json()["affiliate_url"] == product["affiliate_url"]
    assert client.post("/api/products", json=product).status_code == 409
    pid = response.json()["id"]
    assert client.put(f"/api/products/{pid}", json={**product, "title": "Título revisado"}).json()["title"] == "Título revisado"
    for url in ("https://br.shp.ee.evil.example/x", "http://br.shp.ee/x", "https://user@br.shp.ee/x", "https://onelink.shein.com/x", "https://br.shp.ee:bad/x"):
        assert client.post("/api/products", json={**product, "affiliate_url": url}).status_code == 422
    assert client.get("/api/products/99999").status_code == 404


def test_metric_idempotency_ranking_and_aggregation(client):
    login(client)
    data = {"event_id": "real-report-1", "product_id": 1, "views": 3000, "clicks": 150, "conversions": 4, "commission": 50, "spend": 20}
    assert client.post("/api/metrics", json=data).status_code == 201
    duplicate = client.post("/api/metrics", json=data)
    assert duplicate.status_code == 200 and duplicate.json()["duplicate"]
    assert client.post("/api/metrics", json={**data, "commission": 51}).status_code == 409
    assert client.post("/api/metrics", json={**data, "event_id": "negative", "clicks": -1}).status_code == 422
    assert client.post("/api/metrics", json={**data, "event_id": "nan", "commission": "NaN"}).status_code == 422
    assert client.post("/api/metrics", json={**data, "event_id": "manual:1"}).status_code == 422
    ranking = client.get("/api/winners").json()
    row = next(r for r in ranking if r["product"]["id"] == 1)
    assert row["sample_sufficient"] and row["profit"] == 30 and row["recommendation"] == "prioritize"
    assert next(r for r in ranking if r["product"]["id"] == 2)["score"] is None
    assert client.put("/metrics/1", json={"views": 100}).status_code == 200
    assert client.put("/metrics/1", json={"views": 50}).status_code == 200
    assert client.get("/api/dashboard").json()["totals"]["views"] == 3050


def test_creative_edit_and_schedule_require_disclosure(client):
    login(client)
    creative = client.post("/api/creatives", json={"product_id": 1}).json()
    assert creative["type"] == "template_draft" and "afiliado" in creative["caption"]
    cid = creative["id"]
    update = {k: creative[k] for k in ("title", "caption", "prompt", "media_key")}
    assert client.put(f"/api/creatives/{cid}", json={**update, "media_key": "other/private"}).status_code == 422
    assert client.put(f"/api/creatives/{cid}", json={**update, "caption": "Sem identificação"}).status_code == 200
    schedule = {"creative_id": cid, "channel": "pinterest", "scheduled_for": (now() + timedelta(days=1)).isoformat()}
    assert client.post("/api/schedules", json=schedule).status_code == 422
    assert client.put(f"/api/creatives/{cid}", json=update).status_code == 200
    planned = client.post("/api/schedules", json=schedule)
    assert planned.status_code == 201 and planned.json()["status"] == "planned"
    assert planned.json()["external_publication"] == "not_connected"
    assert client.post("/api/schedules", json={**schedule, "scheduled_for": "2020-01-01T12:00:00"}).status_code == 422
    assert client.post("/api/schedules", json={**schedule, "scheduled_for": (now() - timedelta(days=1)).isoformat()}).status_code == 422
    assert len(client.get("/api/schedules").json()) == 1


def test_all_agents_execute_and_persist_results(client):
    login(client)
    agents = client.get("/api/agents").json()["agents"]
    for agent in agents:
        response = client.post(f"/api/agents/{agent}/run", json={"product_id": 1} if agent == "Creative" else {})
        assert response.status_code == 201 and response.json()["agent"] == agent and response.json()["result"]
    assert len(client.get("/api/agent-runs").json()) == 7
    assert len(client.get("/api/creatives").json()) == 1
    assert client.post("/api/agents/Creative/run", json={}).status_code == 422
    assert client.post("/api/agents/Unknown/run", json={}).status_code == 404
    with client.app.state.sessions() as db:
        assert len(list(db.scalars(select(Audit).where(Audit.action.like("agent.%"))))) == 7


def test_restart_keeps_owner_catalog_metrics_and_creatives(setup_app):
    app, url = setup_app
    with TestClient(app) as client:
        login(client)
        assert client.post("/api/metrics", json={"event_id": "persisted", "product_id": 1, "clicks": 10}).status_code == 201
        creative = client.post("/api/creatives", json={"product_id": 1}).json()
        cookie = client.cookies[COOKIE]
    with TestClient(make_app(url)) as client:
        client.cookies.set(COOKIE, cookie)
        assert client.get("/api/auth/me").status_code == 200
        assert len(client.get("/api/products").json()) == 4  # No duplicate seeds on startup.
        assert client.get("/api/dashboard").json()["totals"]["clicks"] == 10
        assert client.get("/api/creatives").json()[0]["id"] == creative["id"]


def test_actual_streamed_body_limit(client):
    def chunks():
        for _ in range(11):
            yield b"x" * 100000
    assert client.post("/api/auth/login", content=chunks()).status_code == 413


def test_optional_integrations_report_missing_configuration(client):
    login(client)
    result = client.get("/api/status").json()
    assert result["redis"] == "not_configured" and result["s3"] == "not_configured"
    assert result["video_generation"] == "not_connected"
    assert client.post("/api/media/uploads", json={"content_type": "image/png"}).status_code == 503
    assert client.post("/api/media/uploads", json={"content_type": "text/html"}).status_code == 422


def test_media_signing_enforces_type_size_and_private_key(client, monkeypatch):
    import boto3
    captured = {}
    class S3:
        def generate_presigned_post(self, **kwargs):
            captured.update(kwargs)
            return {"url": "https://storage.example.test", "fields": {"key": kwargs["Key"]}}
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setattr(boto3, "client", lambda *a, **kw: S3())
    login(client)
    result = client.post("/api/media/uploads", json={"content_type": "image/png"})
    assert result.status_code == 200
    assert captured["Key"].startswith("fluxosolar/") and captured["Key"].endswith(".png")
    assert captured["ExpiresIn"] == 300
    assert ["content-length-range", 1, 25 * 1024 * 1024] in captured["Conditions"]
    assert captured["Fields"]["Content-Type"] == "image/png"
