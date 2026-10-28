"""Offline contract tests: no real DIVERA key, Pi, MongoDB or network required."""

import asyncio
import hashlib
import os
from datetime import timedelta
from unittest.mock import AsyncMock

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "divera_offline_tests")

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from mongomock_motor import AsyncMongoMockClient

from core import admin
from core.time import iso, now_utc
from core.validation import validation_error
from routes import divera as routes
from routes import system_updates
from services import divera, divera_polling as polling, divera_settings as settings


@pytest_asyncio.fixture
async def env(monkeypatch):
    database = AsyncMongoMockClient().test
    for module in (admin, routes, divera, polling, settings):
        monkeypatch.setattr(module, "db", database)
    monkeypatch.setenv("ELS_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("ELS_CONFIG_ENCRYPTION_KEY_FILE", raising=False)
    monkeypatch.delenv("ELS_ADMIN_PASSWORD_HASH_FILE", raising=False)
    monkeypatch.delenv("DIVERA_API_KEY", raising=False)
    salt = b"offline-test-salt"
    digest = hashlib.scrypt(b"test-admin-password", salt=salt, n=16384, r=8, p=1)
    monkeypatch.setenv("ELS_ADMIN_PASSWORD_HASH", f"scrypt${salt.hex()}${digest.hex()}")
    monkeypatch.setattr(polling, "_local_lock", asyncio.Lock())
    monkeypatch.setattr(polling, "ensure_task", lambda: None)
    monkeypatch.setattr(divera, "record_fms_change", AsyncMock())
    monkeypatch.setattr(divera, "publish_incident_event", AsyncMock())
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_error)
    app.include_router(admin.router)
    app.include_router(routes.router)
    app.include_router(system_updates.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield database, client
    await polling.shutdown()


async def authenticate(client):
    response = await client.post(
        "/api/admin/login", json={"password": "test-admin-password"}
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


@pytest.mark.asyncio
async def test_client_role_cannot_change_settings_or_test_keys(env, monkeypatch):
    _, client = env
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(divera, "fetch_vehicles", fetch)
    for path, method, payload in (
        ("test", "post", {"api_key": "secret"}),
        ("key", "put", {"api_key": "secret"}),
        ("interval", "put", {"interval": 10}),
    ):
        response = await getattr(client, method)(
            "/api/divera/settings/" + path,
            json=payload,
            headers={"X-Role": "einsatzleiter"},
        )
        assert response.status_code == 401
        assert "secret" not in response.text
    fetch.assert_not_awaited()
    assert (await client.post("/api/system/updates/apply")).status_code == 401
    assert (await client.post("/api/system/updates/rollback")).status_code == 401


@pytest.mark.asyncio
async def test_login_limit_expiry_logout_and_token_storage(env):
    database, client = env
    headers = await authenticate(client)
    stored = await database.admin_sessions.find_one({})
    assert headers["Authorization"].split()[1] not in repr(stored)
    await database.admin_sessions.update_one(
        {}, {"$set": {"expires_at": iso(now_utc() - timedelta(seconds=1))}}
    )
    assert (await client.post("/api/admin/logout", headers=headers)).status_code == 401
    headers = await authenticate(client)
    assert (await client.post("/api/admin/logout", headers=headers)).status_code == 200
    assert (await client.post("/api/admin/logout", headers=headers)).status_code == 401
    for _ in range(3):
        assert (
            await client.post("/api/admin/login", json={"password": "wrong"})
        ).status_code == 401
    assert (
        await client.post("/api/admin/login", json={"password": "wrong"})
    ).status_code == 429


@pytest.mark.asyncio
async def test_new_key_verified_encrypted_hot_loaded_and_never_returned(
    env, monkeypatch
):
    database, client = env
    headers = await authenticate(client)
    fetch = AsyncMock(return_value=[{"id": 1}])
    monkeypatch.setattr(divera, "fetch_vehicles", fetch)
    assert (
        await client.post(
            "/api/divera/settings/test", headers=headers, json={"api_key": "new-secret"}
        )
    ).status_code == 200
    assert not await database.system_settings.find_one({"_id": "divera"})
    response = await client.put(
        "/api/divera/settings/key",
        headers=headers,
        json={"api_key": "different-secret"},
    )
    assert response.status_code == 200
    fetch.assert_awaited_with(api_key="different-secret")
    assert await settings.current_key() == "different-secret"
    audit = await database.admin_audit.find({}).to_list(None)
    assert any(
        event["action"] == "divera.key.replace" and event["outcome"] == "succeeded"
        for event in audit
    )
    assert "different-secret" not in repr(audit)
    stored = await database.system_settings.find_one({"_id": "divera"})
    assert "different-secret" not in repr(stored)
    assert (
        Fernet(os.environ["ELS_CONFIG_ENCRYPTION_KEY"].encode()).decrypt(
            stored["encrypted_key"].encode()
        )
        == b"different-secret"
    )
    assert "secret" not in response.text
    assert "secret" not in (await client.get("/api/divera/settings")).text
    # No in-memory key cache: a new process reads the same database setting.
    monkeypatch.setenv("DIVERA_API_KEY", "legacy-secret")
    assert await settings.current_key() == "different-secret"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,status", [(401, 422), (403, 422), (500, 502), (429, 502)]
)
async def test_failed_key_validation_keeps_old_key_and_redacts_url(
    env, monkeypatch, failure, status
):
    _, client = env
    await settings.save(key="old-key")
    headers = await authenticate(client)
    request = httpx.Request("GET", "https://divera.invalid/?accesskey=very-sensitive")
    error = httpx.HTTPStatusError(
        "very-sensitive",
        request=request,
        response=httpx.Response(failure, request=request),
    )
    monkeypatch.setattr(divera, "fetch_vehicles", AsyncMock(side_effect=error))
    response = await client.put(
        "/api/divera/settings/key", headers=headers, json={"api_key": "new-key"}
    )
    assert response.status_code == status
    assert "very-sensitive" not in response.text
    assert await settings.current_key() == "old-key"


@pytest.mark.asyncio
async def test_encryption_missing_or_lost_fails_closed_but_key_can_be_replaced(
    env, monkeypatch
):
    _, client = env
    headers = await authenticate(client)
    await settings.save(key="old-key")
    monkeypatch.setenv("ELS_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())
    info = (await client.get("/api/divera/settings")).json()
    assert not info["configured"] and info["configuration_error"]
    monkeypatch.setattr(divera, "fetch_vehicles", AsyncMock(return_value=[]))
    assert (
        await client.put(
            "/api/divera/settings/key", headers=headers, json={"api_key": "replacement"}
        )
    ).status_code == 200
    assert await settings.current_key() == "replacement"
    monkeypatch.delenv("ELS_CONFIG_ENCRYPTION_KEY")
    assert (
        await client.put(
            "/api/divera/settings/key", headers=headers, json={"api_key": "other"}
        )
    ).status_code == 503


@pytest.mark.asyncio
async def test_fixed_intervals_and_legacy_migration(env, monkeypatch):
    _, client = env
    headers = await authenticate(client)
    assert (await client.get("/api/divera/settings")).json()[
        "poll_interval_seconds"
    ] == 30
    for interval in [10, 20, 30, 60, 120, 300]:
        response = await client.put(
            "/api/divera/settings/interval",
            headers=headers,
            json={"interval": interval},
        )
        assert response.status_code == 200
        assert (await settings.settings())["interval"] == interval
    for invalid in [5, 0, 7, 301, True, "10", 10.5]:
        assert (
            await client.put(
                "/api/divera/settings/interval",
                headers=headers,
                json={"interval": invalid},
            )
        ).status_code == 422
    monkeypatch.setenv("DIVERA_API_KEY", "legacy")
    await settings.initialize()
    assert (await settings.settings())["encrypted_key"]
    await settings.save(key="replacement")
    await settings.initialize()
    assert await settings.current_key() == "replacement"


async def seed(database):
    for incident in ["a", "b", "stopped", "archived"]:
        await database.incidents.insert_one(
            {
                "id": incident,
                "divera_enabled": incident != "stopped",
                "status": "abgeschlossen" if incident == "archived" else "aktiv",
            }
        )
        await database.resources.insert_one(
            {
                "id": "resource-" + incident,
                "incident_id": incident,
                "divera_id": "1",
                "fms_status": 1,
                "status": "verfuegbar",
            }
        )


@pytest.mark.asyncio
async def test_concurrent_manual_automatic_and_mapping_share_single_fetch(
    env, monkeypatch
):
    database, client = env
    await seed(database)
    await settings.save(key="dummy")
    in_flight = 0
    peak = 0
    calls = 0

    async def fetch():
        nonlocal in_flight, peak, calls
        calls += 1
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return [{"id": 1, "fmsstatus": 3, "lat": 50, "lng": 8}]

    monkeypatch.setattr(divera, "fetch_vehicles", fetch)
    results = await asyncio.gather(
        polling.sync_incident("a"),
        polling.sync_incident("b"),
        polling.vehicles(),
        polling._cycle(),
    )
    assert results[0]["ok"] and results[1]["ok"]
    assert calls == peak == 1
    for incident in ["a", "b"]:
        resource = await database.resources.find_one({"incident_id": incident})
        assert resource["fms_status"] == 3 and resource["lat"] == 50
    for incident in ["stopped", "archived"]:
        assert (await database.resources.find_one({"incident_id": incident}))[
            "fms_status"
        ] == 1
    response = await client.get("/api/incidents/a/divera/status")
    assert response.status_code == 200 and response.json()["enabled"]
    assert (await client.post("/api/incidents/archived/divera/sync")).status_code == 409
    assert divera.record_fms_change.await_count == 2


@pytest.mark.asyncio
async def test_backoff_persisted_honors_retry_after_and_recovers(env, monkeypatch):
    database, _ = env
    await seed(database)
    request = httpx.Request("GET", "https://divera.invalid/?accesskey=secret")
    error = httpx.HTTPStatusError(
        "secret",
        request=request,
        response=httpx.Response(429, headers={"Retry-After": "600"}, request=request),
    )
    fetch = AsyncMock(side_effect=error)
    monkeypatch.setattr(divera, "fetch_vehicles", fetch)
    assert not (await polling.sync_incident("a"))["ok"]
    state = await polling.state()
    assert state["failures"] == 1 and "secret" not in repr(state)
    assert state["next_at"] > iso(now_utc() + timedelta(seconds=590))
    # Retry remains blocked after recreating local scheduler state.
    monkeypatch.setattr(polling, "_local_lock", asyncio.Lock())
    assert not (await polling.sync_incident("b"))["ok"]
    assert fetch.await_count == 1
    await database.system_settings.update_one(
        {"_id": "divera_poll"},
        {"$set": {"next_at": iso(now_utc() - timedelta(seconds=1))}},
    )
    fetch.side_effect = None
    fetch.return_value = []
    assert (await polling.sync_incident("a"))["ok"]
    assert (await polling.sync_incident("b"))["ok"]  # empty snapshot is valid
    assert fetch.await_count == 2
    assert (await polling.state())["failures"] == 0


@pytest.mark.asyncio
async def test_database_lease_blocks_other_workers_and_recovers_abandoned_lease(
    env, monkeypatch
):
    database, _ = env
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(divera, "fetch_vehicles", fetch)
    await database.system_locks.insert_one(
        {
            "_id": "divera",
            "owner": "other-worker",
            "until": iso(now_utc() + timedelta(seconds=90)),
        }
    )
    assert not (await polling.sync_incident("a"))["ok"]
    fetch.assert_not_awaited()
    await database.system_locks.update_one(
        {}, {"$set": {"until": iso(now_utc() - timedelta(seconds=1))}}
    )
    assert (await polling.sync_incident("a"))["ok"]
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_resume_and_stop_keep_persisted_desire(env, monkeypatch):
    database, _ = env
    await seed(database)
    await settings.save(key="dummy")
    calls = []
    monkeypatch.setattr(polling, "ensure_task", lambda: calls.append(True))
    await polling.resume_active_pollings()
    assert calls
    await polling.stop_polling("a")
    assert not (await database.incidents.find_one({"id": "a"}))["divera_enabled"]
    assert (await database.incidents.find_one({"id": "b"}))["divera_enabled"]
    await polling.start_polling("a")
    assert (await database.incidents.find_one({"id": "a"}))["divera_enabled"]


@pytest.mark.asyncio
async def test_invalid_secret_payloads_are_not_echoed(env):
    _, client = env
    headers = await authenticate(client)
    response = await client.put(
        "/api/divera/settings/key",
        headers=headers,
        json={"api_key": {"secret": "never-echo-this"}},
    )
    assert response.status_code == 422
    assert "never-echo-this" not in response.text
    response = await client.post(
        "/api/admin/login", json={"password": {"secret": "never-echo-this"}}
    )
    assert response.status_code == 422 and "never-echo-this" not in response.text


@pytest.mark.asyncio
async def test_real_transport_uses_updated_key_for_reads_and_fms_without_url_logging(
    env, monkeypatch, caplog
):
    _, _ = env
    seen = []
    original_client = httpx.AsyncClient

    def handler(request):
        seen.append(request.url.params["accesskey"])
        return httpx.Response(200, json={"success": True, "data": []})

    monkeypatch.setattr(
        divera.httpx,
        "AsyncClient",
        lambda **kw: original_client(transport=httpx.MockTransport(handler), **kw),
    )
    await settings.save(key="first-secret")
    await divera.fetch_vehicles()
    await settings.save(key="second-secret")
    await divera.fetch_vehicles()
    await divera.set_vehicle_status("1", 3, "SPRECHEN SIE")
    assert seen == ["first-secret", "second-secret", "second-secret"]
    assert "first-secret" not in caplog.text and "second-secret" not in caplog.text


@pytest.mark.asyncio
async def test_scheduler_runs_only_with_enabled_incidents_and_resumes_persisted_state(
    env, monkeypatch
):
    database, _ = env
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(divera, "fetch_vehicles", fetch)
    original_sleep = asyncio.sleep
    ticks = 0

    async def step(_):
        nonlocal ticks
        ticks += 1
        if ticks == 1:
            fetch.assert_not_awaited()
            await database.incidents.insert_one(
                {"id": "a", "divera_enabled": True, "status": "aktiv"}
            )
        elif ticks == 2:
            fetch.assert_awaited_once()
        else:
            raise asyncio.CancelledError()
        await original_sleep(0)

    monkeypatch.setattr(polling.asyncio, "sleep", step)
    with pytest.raises(asyncio.CancelledError):
        await polling._loop()
    fetch.assert_awaited_once()  # persisted next_at prevents another fetch
