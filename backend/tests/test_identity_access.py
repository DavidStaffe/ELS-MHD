"""End-to-end ASGI authorization tests with an isolated Mongo-compatible store."""

import os
import time
from datetime import timedelta
import importlib
from unittest.mock import AsyncMock

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "identity_tests")

import httpx
import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient
from core import identity, access
from core.time import now_utc, iso
from server import app


@pytest_asyncio.fixture
async def env(monkeypatch):
    database = AsyncMongoMockClient().test
    modules = [
        "core.identity",
        "core.access",
        "core.admin",
        "routes.identity",
        "routes.governance",
        "routes.incidents",
        "routes.patients",
        "routes.resources",
        "routes.messages",
        "routes.patient_disposition",
        "routes.transports",
        "services.seeds",
        "services.funk",
        "services.demo",
    ]
    for name in modules:
        module = importlib.import_module(name)
        if hasattr(module, "db"):
            monkeypatch.setattr(module, "db", database)
    await identity.indexes()
    for uid, permissions, eligible, admin in [
        ("admin", ["users.manage", "settings.manage", "archives.manage"], [], True),
        ("el", ["incidents.create"], ["EL"], False),
        ("other", [], [], False),
        ("assigner", ["incidents.roles.assign"], [], False),
        ("al", [], ["AL"], False),
        ("fa", [], ["FueAss"], False),
        ("doc", [], ["Dokumentar"], False),
    ]:
        await database.users.insert_one(
            {
                "id": uid,
                "username": uid,
                "display_name": uid,
                "password_hash": identity.PASSWORDS.hash("a-secure-password"),
                "active": True,
                "admin": admin,
                "eligible": eligible,
                "permissions": permissions,
                "generation": 0,
                "must_change_password": False,
            }
        )
    await database.incidents.insert_one(
        {
            "id": "i",
            "name": "Einsatz",
            "status": "operativ",
            "created_by": "el",
            "assignments": {"el": {"role": "EL"}},
            "secret": "sensitive",
        }
    )
    await database.patients.insert_one(
        {
            "id": "p",
            "incident_id": "i",
            "status": "in_behandlung",
            "name": "patient-secret",
            "abschnitt_id": "s",
        }
    )
    await database.abschnitte.insert_one({"id": "s", "incident_id": "i"})
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        yield database, client


async def login(client, username):
    response = await client.post(
        "/api/auth/login", json={"username": username, "password": "a-secure-password"}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return response


@pytest.mark.asyncio
async def test_no_anonymous_api_or_direct_patient_access(env):
    _, c = env
    for path in [
        "/api/incidents",
        "/api/patients/p",
        "/api/incidents/i/patients",
        "/api/incidents/i/report",
        "/api/incidents/i/patients/stream",
        "/api/system/updates/status",
    ]:
        assert (await c.get(path)).status_code == 401, path


@pytest.mark.asyncio
async def test_admin_is_not_operational_reader_and_overview_redacts(env):
    _, c = env
    await login(c, "admin")
    assert (await c.get("/api/patients/p")).status_code == 403
    result = (await c.get("/api/incidents")).json()
    assert result == [
        {"id": "i", "name": "Einsatz", "status": "operativ", "restricted": True}
    ]
    assert (await c.get("/api/incidents/i/report")).status_code == 403


@pytest.mark.asyncio
async def test_csrf_lock_inactivity_and_deactivation(env):
    db, c = env
    await login(c, "el")
    csrf = c.headers.pop("X-CSRF-Token")
    assert (await c.post("/api/auth/lock")).status_code == 403
    c.headers["X-CSRF-Token"] = csrf
    await db.auth_sessions.update_many({}, {"$set": {"activity": time.time() - 601}})
    assert (await c.get("/api/patients/p")).status_code == 423
    assert (await c.post("/api/auth/activity")).status_code == 423
    assert (await c.get("/api/auth/me")).json()["locked"] is True
    assert (
        await c.post("/api/auth/unlock", json={"password": "a-secure-password"})
    ).status_code == 200
    assert (await c.get("/api/patients/p")).status_code == 200
    await db.users.update_one({"id": "el"}, {"$set": {"active": False}})
    assert (await c.get("/api/patients/p")).status_code == 401


@pytest.mark.asyncio
async def test_creation_requires_eligible_initial_el(env):
    db, c = env
    await login(c, "el")
    r = await c.post(
        "/api/incidents", json={"name": "Neuer Einsatz", "el_user_id": "other"}
    )
    assert r.status_code == 422
    r = await c.post(
        "/api/incidents", json={"name": "Neuer Einsatz", "el_user_id": "el"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["created_by"] == "el"
    assert r.json()["assignments"] == {"el": {"role": "EL"}}


@pytest.mark.asyncio
async def test_appointments_el_cannot_appoint_fa_and_global_cannot_appoint_doc(env):
    db, c = env
    await login(c, "el")
    assert (
        await c.put(
            "/api/incidents/i/assignments",
            json={
                "user_id": "fa",
                "role": "FueAss",
                "supports": "EL",
                "reason": "Ernennung",
            },
        )
    ).status_code == 403
    assert (
        await c.put(
            "/api/incidents/i/assignments",
            json={
                "user_id": "al",
                "role": "AL",
                "section_id": "s",
                "reason": "Ernennung",
            },
        )
    ).status_code == 200
    await login(c, "assigner")
    assert (
        await c.put(
            "/api/incidents/i/assignments",
            json={"user_id": "doc", "role": "Dokumentar", "reason": "Ernennung"},
        )
    ).status_code == 403
    assert (
        await c.put(
            "/api/incidents/i/assignments",
            json={
                "user_id": "fa",
                "role": "FueAss",
                "supports": "EL",
                "reason": "Ernennung",
            },
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_close_snapshot_no_operational_side_effects_and_reopen(env):
    db, c = env
    await login(c, "el")
    assert (
        await c.patch("/api/incidents/i", json={"status": "abgeschlossen"})
    ).status_code == 409
    assert (
        await c.post("/api/incidents/i/close", json={"reason": "Einsatzende"})
    ).status_code == 409
    r = await c.post(
        "/api/incidents/i/close", json={"reason": "Einsatzende", "confirm_open": True}
    )
    assert r.status_code == 200, r.text
    assert (await db.patients.find_one({"id": "p"}))["status"] == "in_behandlung"
    assert (
        await c.patch("/api/patients/p", json={"name": "change"})
    ).status_code == 409
    assert (
        await c.post("/api/incidents/i/reopen", json={"reason": "Fortführung"})
    ).status_code == 200
    assert (await db.incidents.find_one({"id": "i"}))["assignments"] == {
        "el": {"role": "EL"}
    }


@pytest.mark.asyncio
async def test_archive_grants_expire_and_correction_requires_both_rights(env):
    db, c = env
    await db.incidents.update_one(
        {"id": "i"}, {"$set": {"status": "abgeschlossen", "assignments": {}}}
    )
    await db.users.update_one(
        {"id": "doc"},
        {"$set": {"permissions": ["archives.patients.correct", "patients.read"]}},
    )
    await login(c, "doc")
    payload = {"reason": "Dokumentationsfehler", "changes": {"name": "Korrigiert"}}
    assert (
        await c.post("/api/incidents/i/corrections/patients/p", json=payload)
    ).status_code == 403
    await db.archive_grants.insert_one(
        {
            "incident_id": "i",
            "user_id": "doc",
            "revoked": False,
            "expires_at": iso(now_utc() + timedelta(days=1)),
        }
    )
    assert (
        await c.post("/api/incidents/i/corrections/patients/p", json=payload)
    ).status_code == 200
    patient = await db.patients.find_one({"id": "p"})
    assert patient["versions"][0]["before"]["name"] == "patient-secret"
    assert patient["versions"][0]["user_id"] == "doc"
    assert (
        await c.post(
            "/api/incidents/i/corrections/patients/p",
            json={"reason": "Manipulation", "changes": {"status": "entlassen"}},
        )
    ).status_code == 422
    await db.archive_grants.update_many(
        {}, {"$set": {"expires_at": iso(now_utc() - timedelta(seconds=1))}}
    )
    assert (await c.get("/api/patients/p")).status_code == 403


@pytest.mark.asyncio
async def test_last_admin_and_forced_password_change(env):
    db, c = env
    await login(c, "admin")
    assert (
        await c.post(
            "/api/auth/users/admin/deactivate",
            json={"reason": "Sperrung", "emergency": True},
        )
    ).status_code == 409
    await db.users.update_one({"id": "admin"}, {"$set": {"must_change_password": True}})
    assert (await c.get("/api/auth/users")).status_code == 428
    assert (
        await c.post("/api/auth/password", json={"password": "my-new-secure-password"})
    ).status_code == 200
    assert (await c.get("/api/auth/users")).status_code == 200


@pytest.mark.asyncio
async def test_cookie_flags_logout_revocation_and_no_legacy_login(env):
    db, c = env
    r = await login(c, "el")
    cookie = r.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert "domain=" not in cookie
    token = c.cookies.get(identity.COOKIE)
    assert not await db.auth_sessions.find_one({"_id": token})
    assert await db.auth_sessions.find_one({"_id": identity.digest(token)})
    assert (
        await c.post("/api/admin/login", json={"password": "legacy"})
    ).status_code == 410
    assert (await c.post("/api/auth/logout")).status_code == 200
    c.cookies.set(identity.COOKIE, token)
    assert (await c.get("/api/patients/p")).status_code == 401


@pytest.mark.asyncio
async def test_account_reset_and_generation_revoke_sessions(env):
    db, c = env
    await login(c, "admin")
    r = await c.post("/api/auth/users/el/reset")
    assert r.status_code == 200
    value = r.json()["initial_password"]
    user = await db.users.find_one({"id": "el"})
    assert user["password_hash"].startswith("$argon2id$")
    assert identity.verify(value, user["password_hash"])
    assert user["must_change_password"] is True
    assert "password_hash" not in (await c.get("/api/auth/users")).text
    assert (
        await c.put(
            "/api/auth/users/admin",
            json={"display_name": "Administrator", "eligible": [], "permissions": []},
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_rate_limit_and_origin_checks(env):
    _, c = env
    assert (
        await c.post(
            "/api/auth/login",
            headers={"Origin": "https://attacker.invalid"},
            json={"username": "el", "password": "a-secure-password"},
        )
    ).status_code == 403
    for _ in range(5):
        assert (
            await c.post(
                "/api/auth/login", json={"username": "el", "password": "wrong"}
            )
        ).status_code == 401
    assert (
        await c.post(
            "/api/auth/login", json={"username": "el", "password": "a-secure-password"}
        )
    ).status_code == 429
    assert not identity.has(
        {"permissions": ["unknown.permission"]}, "unknown.permission"
    )


@pytest.mark.asyncio
async def test_global_closer_does_not_give_last_el_reopen_right(env):
    db, c = env
    await db.users.update_one(
        {"id": "other"}, {"$set": {"permissions": ["incidents.close"]}}
    )
    await login(c, "other")
    assert (
        await c.post(
            "/api/incidents/i/close",
            json={"reason": "Globaler Abschluss", "confirm_open": True},
        )
    ).status_code == 200
    await login(c, "el")
    assert (
        await c.post("/api/incidents/i/reopen", json={"reason": "Wiederaufnahme"})
    ).status_code == 403
    assert (await c.get("/api/patients/p")).status_code == 200  # Creator lifetime read.


@pytest.mark.asyncio
async def test_documentarian_medical_separation_and_own_corrections(env):
    db, c = env
    await db.incidents.update_one(
        {"id": "i"}, {"$set": {"assignments.doc": {"role": "Dokumentar"}}}
    )
    await login(c, "doc")
    assert (await c.get("/api/patients/p")).status_code == 403
    response = await c.post(
        "/api/incidents/i/messages",
        json={"text": "Lagemeldung", "von": "Funk", "erfasst_von": "forged-name"},
    )
    assert response.status_code == 201, response.text
    entry = response.json()
    assert entry["created_by"] == "doc" and entry["erfasst_von"] == "doc"
    assert entry["category"] == "central" and entry["abschnitt_id"] is None
    path = f"/api/incidents/i/corrections/messages/{entry['id']}"
    assert (
        await c.post(path, json={"reason": "   ", "changes": {"text": "Fehler"}})
    ).status_code == 422
    assert (
        await c.post(
            path, json={"reason": "Richtigstellung", "changes": {"text": "Richtig"}}
        )
    ).status_code == 200
    assert (
        await c.post(
            path, json={"reason": "Umkategorisierung", "changes": {"abschnitt_id": "s"}}
        )
    ).status_code == 422
    await db.messages.update_one({"id": entry["id"]}, {"$set": {"created_by": "el"}})
    assert (
        await c.post(
            path, json={"reason": "Fremdkorrektur", "changes": {"text": "Fremd"}}
        )
    ).status_code == 403
    assert (
        await c.patch("/messages/" + entry["id"], json={"text": "Unbegründet"})
    ).status_code in {404, 405}


@pytest.mark.asyncio
async def test_helper_current_resource_scope_and_no_self_assignment(env):
    db, c = env
    await db.users.update_one(
        {"id": "other"}, {"$set": {"permissions": ["helpers.patients.update"]}}
    )
    await db.incidents.update_one(
        {"id": "i"},
        {"$set": {"assignments.other": {"role": "Helfer", "resource_id": "r"}}},
    )
    await db.resources.insert_one(
        {
            "id": "r",
            "incident_id": "i",
            "bound_patient_id": "p",
            "name": "Eigene Ressource",
        }
    )
    await db.resources.insert_one(
        {"id": "foreign", "incident_id": "i", "name": "Fremde Ressource"}
    )
    await db.patients.insert_one({"id": "foreign-p", "incident_id": "i"})
    await login(c, "other")
    assert (await c.get("/api/patients/p")).status_code == 200
    assert (await c.get("/api/patients/foreign-p")).status_code == 403
    assert (
        await c.patch("/api/patients/p", json={"notiz": "Verlauf aktualisiert"})
    ).status_code == 200
    assert [p["id"] for p in (await c.get("/api/incidents/i/patients")).json()] == ["p"]
    assert [r["id"] for r in (await c.get("/api/incidents/i/resources")).json()] == [
        "r"
    ]
    assert (
        await c.post("/api/patients/p/assign-resource", json={"resource_id": "foreign"})
    ).status_code == 403
    assert (
        await c.put(
            "/api/incidents/i/assignments",
            json={
                "user_id": "other",
                "role": "Helfer",
                "resource_id": "foreign",
                "reason": "Selbstzuordnung",
            },
        )
    ).status_code == 403
    await db.resources.update_one(
        {"id": "r"}, {"$set": {"bound_patient_id": "foreign-p"}}
    )
    assert (await c.get("/api/patients/p")).status_code == 403


@pytest.mark.asyncio
async def test_section_leader_cannot_assign_helpers_or_write_foreign_section(env):
    db, c = env
    await db.incidents.update_one(
        {"id": "i"}, {"$set": {"assignments.al": {"role": "AL", "section_id": "s"}}}
    )
    await login(c, "al")
    assert (await c.get("/api/patients/p")).status_code == 200
    own_transport = await c.post("/api/incidents/i/transports", json={"patient_id": "p", "typ": "intern", "ziel": "uhs"})
    assert own_transport.status_code == 201, own_transport.text
    assert (
        await c.patch("/api/patients/p", json={"abschnitt_id": "foreign"})
    ).status_code in {403, 422}
    assert (
        await c.put(
            "/api/incidents/i/assignments",
            json={
                "user_id": "other",
                "role": "Helfer",
                "resource_id": "r",
                "reason": "Helferzuordnung",
            },
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_assignment_limits_and_organizational_support_changes(env):
    db, c = env
    from routes.governance import validate_assignments

    with pytest.raises(Exception) as error:
        validate_assignments(
            {
                "e": {"role": "EL"},
                **{str(n): {"role": "FueAss", "supports": "EL"} for n in range(3)},
            }
        )
    assert error.value.status_code == 409
    await db.incidents.update_one(
        {"id": "i"},
        {
            "$set": {
                "assignments.fa": {"role": "FueAss", "supports": "EL"},
                "assignments.al": {"role": "AL", "section_id": "s"},
            }
        },
    )
    await login(c, "el")
    r = await c.put(
        "/api/incidents/i/assistants/fa/support",
        json={"supports": "AL", "section_id": "s", "reason": "Abschnitt unterstützen"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignments"]["fa"]["role"] == "FueAss"


@pytest.mark.asyncio
async def test_emergency_disable_works_despite_leadership(env):
    db, c = env
    await login(c, "admin")
    assert (
        await c.post(
            "/api/auth/users/el/deactivate", json={"reason": "Normale Sperrung"}
        )
    ).status_code == 409
    r = await c.post(
        "/api/auth/users/el/deactivate",
        json={"reason": "Sicherheitsvorfall", "emergency": True},
    )
    assert r.status_code == 200 and r.json()["pending_handover"] == ["i"]
    assert (await db.users.find_one({"id": "el"}))["active"] is False


@pytest.mark.asyncio
async def test_setup_fail_closed_and_recovery_rotation(env, tmp_path, monkeypatch):
    db, c = env
    import json
    import identity_setup

    monkeypatch.setattr(identity_setup, "db", db)
    path = tmp_path / "identity-state.json"
    monkeypatch.setenv("ELS_IDENTITY_STATE_FILE", str(path))
    body = {"code": "setup-secret", "username": "root", "display_name": "Administrator"}
    assert (await c.post("/api/auth/setup", json=body)).status_code == 503
    path.write_text(json.dumps({"setup_id": "setup-id", "state": "pending"}))
    assert (
        await c.post("/api/auth/setup", json=body)
    ).status_code == 403  # Missing DB never opens setup.
    await db.identity_state.insert_one(
        {
            "_id": "setup",
            "setup_id": "setup-id",
            "state": "pending",
            "setup_hash": identity.digest("setup-secret"),
        }
    )
    result = await c.post("/api/auth/setup", json=body)
    assert result.status_code == 200, result.text
    codes = result.json()
    assert json.loads(path.read_text())["state"] == "complete"
    assert (await c.post("/api/auth/setup", json=body)).status_code == 403
    r = await c.post(
        "/api/auth/recover", json={"username": "root", "code": codes["recovery_code"]}
    )
    assert r.status_code == 200 and r.json()["recovery_code"] != codes["recovery_code"]
    assert (
        await c.post(
            "/api/auth/recover",
            json={"username": "root", "code": codes["recovery_code"]},
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_already_open_stream_must_recheck_lock_and_revocation(env):
    db, c = env
    from starlette.requests import Request

    await login(c, "el")
    token = c.cookies.get(identity.COOKIE)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "headers": [(b"cookie", f"{identity.COOKIE}={token}".encode())],
        }
    )
    assert await identity.stream_authorized(request, "i") is True
    await db.auth_sessions.update_many({}, {"$set": {"locked": True}})
    assert await identity.stream_authorized(request, "i") is False

    await db.auth_sessions.update_many({}, {"$set": {"locked": False}})
    await db.users.update_one({"id": "el"}, {"$inc": {"generation": 1}})
    assert await identity.stream_authorized(request, "i") is False


@pytest.mark.asyncio
async def test_request_size_is_bounded_before_json_parsing(env):
    _, c = env
    assert (
        await c.post(
            "/api/auth/login",
            content=b"x" * (2 * 1024 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )
    ).status_code == 413

    async def chunks():
        yield b"{" + b" " * (1024 * 1024)
        yield b" " * (1024 * 1024 + 1) + b"}"

    assert (
        await c.post(
            "/api/auth/login",
            content=chunks(),
            headers={"Content-Type": "application/json"},
        )
    ).status_code == 413


@pytest.mark.asyncio
async def test_demo_has_initial_el_before_seed(env, monkeypatch):
    db, c = env
    from services import demo

    monkeypatch.setattr(demo, "seed_default_resources", AsyncMock())
    monkeypatch.setattr(demo, "_seed_demo_data", AsyncMock())
    await login(c, "el")
    response = await c.post("/api/incidents/demo")
    assert response.status_code == 201, response.text
    record = await db.incidents.find_one({"id": response.json()["id"]})
    assert record["created_by"] == "el"
    assert record["assignments"] == {"el": {"role": "EL"}}


@pytest.mark.asyncio
async def test_lifecycle_realtime_audit_and_preserved_operational_documents(
    env, monkeypatch
):
    from routes import governance

    db, c = env
    publish = AsyncMock()
    monkeypatch.setattr(governance, "publish_incident_event", publish)
    await db.incidents.update_one(
        {"id": "i"},
        {
            "$set": {
                "assignments": {"el": {"role": "EL"}, "doc": {"role": "Dokumentar"}},
                "start_at": "2026-10-29T08:00:00+00:00",
            }
        },
    )
    await db.resources.insert_one(
        {"id": "r", "incident_id": "i", "bound_patient_id": "p", "status": "im_einsatz"}
    )
    await db.transports.insert_one(
        {"id": "t", "incident_id": "i", "status": "unterwegs"}
    )
    before = {
        name: await db[name].find({}, {"_id": 0}).to_list(None)
        for name in ("patients", "resources", "transports")
    }
    await login(c, "el")
    for reason in ("", "   "):
        assert (
            await c.post(
                "/api/incidents/i/close", json={"reason": reason, "confirm_open": True}
            )
        ).status_code == 422
    assert (
        await c.post("/api/incidents/i/close", json={"reason": "Einsatzende"})
    ).status_code == 409
    publish.assert_not_awaited()
    assert (
        await c.post(
            "/api/incidents/i/close",
            json={"reason": "Einsatzende", "confirm_open": True},
        )
    ).status_code == 200
    assert publish.await_args.args[0]["action"] == "closed"
    closed = await db.incidents.find_one({"id": "i"})
    assert closed["assignments"] == {}
    assert closed["closure_open_snapshot"]["resources"][0]["id"] == "r"
    assert (
        await c.post(
            "/api/incidents/i/close", json={"reason": "Doppelt", "confirm_open": True}
        )
    ).status_code == 403
    assert publish.await_count == 1
    assert (
        await c.post("/api/incidents/i/reopen", json={"reason": "Fortführung"})
    ).status_code == 200
    assert publish.await_args.args[0]["action"] == "reopened"
    incident = await db.incidents.find_one({"id": "i"})
    assert incident["assignments"] == {"el": {"role": "EL"}}
    assert incident["start_at"] == "2026-10-29T08:00:00+00:00"
    assert incident["end_at"] is None
    assert [
        (e["action"], e["user_id"], e["reason"]) for e in incident["security_history"]
    ] == [
        ("incident.close", "el", "Einsatzende"),
        ("incident.reopen", "el", "Fortführung"),
    ]
    assert all(e["at"] and e["display_name"] for e in incident["security_history"])
    for name, documents in before.items():
        assert await db[name].find({}, {"_id": 0}).to_list(None) == documents
    assert publish.await_count == 2


@pytest.mark.asyncio
async def test_global_close_capability_on_restricted_list_without_content_access(env):
    db, c = env
    await db.users.update_one(
        {"id": "other"}, {"$set": {"permissions": ["incidents.close"]}}
    )
    await login(c, "other")
    listing = (await c.get("/api/incidents")).json()
    assert listing == [
        {
            "id": "i",
            "name": "Einsatz",
            "status": "operativ",
            "restricted": True,
            "can_close": True,
        }
    ]
    assert (await c.get("/api/incidents/i")).status_code == 403
    assert (
        await c.post(
            "/api/incidents/i/close",
            json={"reason": "Globaler Abschluss", "confirm_open": True},
        )
    ).status_code == 200
    assert (
        await c.post("/api/incidents/i/reopen", json={"reason": "Keine Berechtigung"})
    ).status_code == 403


@pytest.mark.asyncio
async def test_reopen_checks_previous_el_eligibility_and_requires_explicit_global_replacement(
    env,
):
    db, c = env
    await login(c, "el")
    assert (
        await c.post(
            "/api/incidents/i/close",
            json={"reason": "Einsatzende", "confirm_open": True},
        )
    ).status_code == 200
    await db.users.update_one({"id": "el"}, {"$set": {"eligible": []}})
    assert (
        await c.post("/api/incidents/i/reopen", json={"reason": "Fortführung"})
    ).status_code == 403
    assert (await db.incidents.find_one({"id": "i"}))["status"] == "abgeschlossen"
    await db.users.update_one(
        {"id": "other"},
        {
            "$set": {
                "permissions": ["incidents.reopen", "incidents.roles.assign"],
                "eligible": ["EL"],
            }
        },
    )
    await login(c, "other")
    assert (
        await c.post(
            "/api/incidents/i/reopen",
            json={"reason": "Fortführung", "el_user_id": "other"},
        )
    ).status_code == 200
    assert (await db.incidents.find_one({"id": "i"}))["assignments"] == {
        "other": {"role": "EL"}
    }
