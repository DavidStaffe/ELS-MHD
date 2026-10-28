"""API security tests use an isolated fake database and fake local agent."""

import os
from unittest.mock import AsyncMock

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "offline_tests")
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from mongomock_motor import AsyncMongoMockClient
from core import admin
from core.validation import validation_error
from routes import system_updates as routes


@pytest_asyncio.fixture
async def client(monkeypatch):
    database = AsyncMongoMockClient().test
    monkeypatch.setattr(admin, "db", database)
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_error)
    app.include_router(routes.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as value:
        yield app, value, database


@pytest.mark.asyncio
async def test_unauthorized_cannot_call_agent(client, monkeypatch):
    app, http, _ = client
    proxy = AsyncMock()
    monkeypatch.setattr(routes, "agent", proxy)
    for action in ("apply", "rollback"):
        for headers in ({}, {"X-Role": "admin"}, {"Authorization": "Bearer fake"}):
            response = await http.post(
                "/api/system/updates/" + action,
                json={"password": "secret", "version": "v2", "release_id": "a" * 64},
                headers=headers,
            )
            assert response.status_code == 401
    proxy.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_step_up_is_forwarded_once_and_audited(client, monkeypatch):
    app, http, database = client
    app.dependency_overrides[admin.require_admin] = lambda: "synthetic-admin"
    proxy = AsyncMock(return_value={"state": "queued"})
    monkeypatch.setattr(routes, "agent", proxy)
    result = await http.post(
        "/api/system/updates/apply",
        json={"password": "test-only-secret", "version": "v2", "release_id": "a" * 64},
    )
    assert result.status_code == 202
    proxy.assert_awaited_once_with(
        "apply", password="test-only-secret", version="v2", release_id="a" * 64
    )
    records = await database.admin_audit.find().to_list(None)
    assert [r["outcome"] for r in records] == ["requested", "accepted"]
    assert "test-only-secret" not in str(records)


@pytest.mark.asyncio
async def test_unknown_fields_and_passwords_not_echoed(client):
    app, http, _ = client
    app.dependency_overrides[admin.require_admin] = lambda: "synthetic-admin"
    result = await http.post(
        "/api/system/updates/apply",
        json={"password": "SECRET", "version": "../../bad", "command": "SECRET"},
    )
    assert result.status_code == 422
    assert "SECRET" not in result.text


@pytest.mark.asyncio
async def test_unconfigured_agent_fails_closed(client, monkeypatch):
    _, http, _ = client
    monkeypatch.delenv("ELS_UPDATE_SOCKET", raising=False)
    assert (await http.get("/api/system/updates/status")).json()["configured"] is False
    assert (await http.get("/api/system/updates/check")).status_code == 503


def test_maintenance_is_persistent_and_unreadable_fails_closed(tmp_path, monkeypatch):
    from core.maintenance import in_maintenance

    path = tmp_path / "status.json"
    monkeypatch.setenv("ELS_MAINTENANCE_FILE", str(path))
    assert in_maintenance()
    path.write_text('{"maintenance":false}')
    assert not in_maintenance()
    path.write_text('{"maintenance":true}')
    assert in_maintenance()
    path.write_text("invalid")
    assert in_maintenance()
