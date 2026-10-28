"""Personal login, password rotation, workstation lock and account administration."""

import secrets
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, SecretStr, ConfigDict, field_validator

from core.identity import (
    db,
    PASSWORDS,
    COOKIE,
    PERMISSIONS,
    ROLES,
    audit,
    digest,
    has,
    identity,
    limit,
    new_session,
    public_user,
    require,
    password_hash,
    password_verify,
)

router = APIRouter(prefix="/api/auth", tags=["identity"])


class Setup(BaseModel):
    code: SecretStr = Field(max_length=1024)
    username: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    display_name: str = Field(min_length=2, max_length=120)


@router.post("/setup")
async def setup(payload: Setup):
    import json
    from identity_setup import marker_path

    await limit("setup", maximum=5, seconds=3600)
    try:
        marker = json.loads(marker_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(
            503, "Setup ist gesperrt; lokale Einrichtung prüfen."
        ) from None
    state = await db.identity_state.find_one(
        {"_id": "setup", "state": "pending", "setup_id": marker.get("setup_id")}
    )
    if (
        marker.get("state") != "pending"
        or not state
        or digest(payload.code.get_secret_value()) != state.get("setup_hash")
    ):
        raise HTTPException(403, "Setup nicht verfügbar oder Code ungültig.")
    # Claim is permanent even if a subsequent write fails. Never reopen on error.
    claim = await db.identity_state.update_one(
        {"_id": "setup", "state": "pending"},
        {"$set": {"state": "claimed"}, "$unset": {"setup_hash": ""}},
    )
    if not claim.modified_count:
        raise HTTPException(409, "Setup bereits verwendet.")
    password, recovery = secrets.token_urlsafe(18), secrets.token_urlsafe(32)
    user = {
        "id": str(uuid.uuid4()),
        "username": payload.username.lower(),
        "display_name": payload.display_name,
        "active": True,
        "admin": True,
        "permissions": ["users.manage", "settings.manage", "archives.manage"],
        "eligible": [],
        "generation": 0,
        "must_change_password": True,
        "password_hash": await password_hash(password),
        "recovery_hash": await password_hash(recovery),
    }
    await db.users.insert_one(user)
    await db.identity_state.update_one(
        {"_id": "setup", "state": "claimed"}, {"$set": {"state": "complete"}}
    )
    path = marker_path()
    with path.open("w", encoding="utf-8") as f:
        json.dump({"setup_id": state["setup_id"], "state": "complete"}, f)
        f.flush()
        import os

        os.fsync(f.fileno())
    await audit(user, "setup.complete")
    return {"initial_password": password, "recovery_code": recovery}


class Recovery(BaseModel):
    username: str = Field(max_length=80)
    code: SecretStr = Field(max_length=1024)


@router.post("/recover")
async def recover(payload: Recovery):
    await limit("recovery-global", maximum=5, seconds=3600)
    user = await db.users.find_one(
        {"username": payload.username.lower(), "active": True, "admin": True}
    )
    encoded = user.get("recovery_hash", DUMMY_HASH) if user else DUMMY_HASH
    if not await password_verify(payload.code.get_secret_value(), encoded) or not user:
        await audit({"username": payload.username.lower()}, "recovery.denied")
        raise HTTPException(403, "Wiederherstellung fehlgeschlagen.")
    password, recovery = secrets.token_urlsafe(18), secrets.token_urlsafe(32)
    result = await db.users.update_one(
        {"id": user["id"], "recovery_hash": encoded},
        {
            "$set": {
                "password_hash": await password_hash(password),
                "recovery_hash": await password_hash(recovery),
                "must_change_password": True,
            },
            "$inc": {"generation": 1},
        },
    )
    if not result.modified_count:
        raise HTTPException(409, "Code wurde bereits verwendet.")
    await db.auth_sessions.delete_many({"user_id": user["id"]})
    await audit(user, "recovery.used")
    return {"initial_password": password, "recovery_code": recovery}


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: SecretStr = Field(max_length=1024)


class Password(BaseModel):
    password: SecretStr = Field(min_length=12, max_length=1024)
    current_password: SecretStr | None = Field(default=None, max_length=1024)


class Reauth(BaseModel):
    password: SecretStr = Field(max_length=1024)


@router.post("/login")
async def login(payload: Credentials, request: Request, response: Response):
    await limit("login-global", maximum=100)
    await limit("login:" + payload.username.lower())
    user = await db.users.find_one(
        {"username": payload.username.lower(), "active": True}, {"_id": 0}
    )
    # Same Argon2 work for unknown and disabled users.
    encoded = user["password_hash"] if user else DUMMY_HASH
    valid = await password_verify(payload.password.get_secret_value(), encoded)
    if not user or not valid:
        await audit({"username": payload.username.lower()}, "login.denied")
        raise HTTPException(401, "Anmeldung fehlgeschlagen.")
    csrf = await new_session(user, response)
    await audit(user, "login")
    return {"user": public_user(user), "csrf": csrf, "locked": False}


DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


@router.get("/me")
async def me(request: Request):
    user = await identity(request, allow_locked=True, allow_change=True)
    if request.state.locked:
        return {"locked": True, "csrf": request.state.session["csrf"]}
    incidents = await db.incidents.find(
        {
            "status": {"$ne": "abgeschlossen"},
            f"assignments.{user['id']}": {"$exists": True},
        },
        {"_id": 0, "id": 1, "assignments": 1},
    ).to_list(None)
    assignments = {inc["id"]: inc["assignments"][user["id"]] for inc in incidents}
    from core.time import now_utc, iso
    import json

    grants = await db.archive_grants.find(
        {
            "user_id": user["id"],
            "revoked": False,
            "expires_at": {"$gt": iso(now_utc())},
        },
        {"_id": 0, "incident_id": 1},
    ).to_list(None)
    query = (
        {}
        if has(user, "incidents.all.read")
        else {
            "$or": [
                {"created_by": user["id"]},
                {"id": {"$in": list(assignments) + [g["incident_id"] for g in grants]}},
            ]
        }
    )
    readable = await db.incidents.find(query, {"_id": 0, "id": 1}).to_list(None)
    bindings = []
    for assignment in assignments.values():
        if assignment["role"] == "Helfer":
            resource = await db.resources.find_one(
                {"id": assignment.get("resource_id")}, {"_id": 0, "bound_patient_id": 1}
            )
            bindings.append(resource or {})
    access_version = digest(
        json.dumps(
            {
                "readable": sorted(i["id"] for i in readable),
                "assignments": assignments,
                "bindings": bindings,
            },
            sort_keys=True,
        )
    )
    return {
        "user": public_user(user),
        "csrf": request.state.session["csrf"],
        "locked": False,
        "assignments": assignments,
        "access_version": access_version,
    }


@router.get("/events")
async def anonymous_events(request: Request):
    import asyncio
    from fastapi.responses import StreamingResponse
    from services.realtime import subscribe_incidents, unsubscribe_incidents

    await identity(request, allow_locked=True, allow_change=True)
    queue = subscribe_incidents()

    async def events():
        try:
            while not await request.is_disconnected():
                try:
                    await asyncio.wait_for(queue.get(), timeout=20)
                    await identity(request, allow_locked=True, allow_change=True)
                    yield 'event: changed\ndata: {"message":"Neue Ereignisse vorhanden"}\n\n'
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except HTTPException:
                    break
        finally:
            unsubscribe_incidents(queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    user = await identity(request, allow_locked=True, allow_change=True)
    await db.auth_sessions.delete_one({"_id": request.state.session["_id"]})
    response.delete_cookie(
        COOKIE, secure=True, httponly=True, samesite="strict", path="/"
    )
    await audit(user, "logout")
    return {"ok": True}


@router.post("/lock")
async def lock(request: Request):
    user = await identity(request, allow_locked=True, allow_change=True)
    await db.auth_sessions.update_one(
        {"_id": request.state.session["_id"]}, {"$set": {"locked": True}}
    )
    await audit(user, "workstation.lock")
    return {"locked": True}


@router.post("/unlock")
async def unlock(payload: Reauth, request: Request):
    user = await identity(request, allow_locked=True, allow_change=True)
    await limit("unlock:" + user["id"])
    if not await password_verify(
        payload.password.get_secret_value(), user["password_hash"]
    ):
        await audit(user, "workstation.unlock.denied")
        raise HTTPException(401, "Entsperren fehlgeschlagen.")
    await db.auth_sessions.update_one(
        {"_id": request.state.session["_id"]},
        {"$set": {"locked": False, "activity": time.time()}},
    )
    await audit(user, "workstation.unlock")
    return {"ok": True}


@router.post("/activity")
async def activity(request: Request):
    await identity(request)
    await db.auth_sessions.update_one(
        {"_id": request.state.session["_id"], "locked": False},
        {"$set": {"activity": time.time()}},
    )
    return {"ok": True}


@router.post("/reauth")
async def reauthenticate(payload: Reauth, request: Request):
    user = await identity(request)
    await limit("reauth:" + user["id"])
    if not await password_verify(
        payload.password.get_secret_value(), user["password_hash"]
    ):
        raise HTTPException(403, "Passwortprüfung fehlgeschlagen.")
    await audit(user, "reauth")
    return {"ok": True}


@router.get("/capabilities")
async def capabilities(request: Request):
    user = await identity(request)
    require(user, "users.manage")
    return {"permissions": sorted(PERMISSIONS), "eligible": sorted(ROLES - {"Helfer"})}


@router.post("/password")
async def password(payload: Password, request: Request, response: Response):
    user = await identity(request, allow_change=True)
    if not user.get("must_change_password"):
        await limit("password-change:" + user["id"])
        if not payload.current_password or not await password_verify(
            payload.current_password.get_secret_value(), user["password_hash"]
        ):
            raise HTTPException(403, "Aktuelles Passwort erforderlich.")
    value = payload.password.get_secret_value()
    if await password_verify(value, user["password_hash"]):
        raise HTTPException(422, "Bitte ein neues Passwort wählen.")
    changed = await db.users.update_one(
        {"id": user["id"], "generation": user.get("generation", 0), "active": True},
        {
            "$set": {
                "password_hash": await password_hash(value),
                "must_change_password": False,
            },
            "$inc": {"generation": 1},
        },
    )
    if not changed.modified_count:
        raise HTTPException(409, "Konto wurde geändert. Neu anmelden.")
    await db.auth_sessions.delete_many({"user_id": user["id"]})
    user = await db.users.find_one(
        {"id": user["id"], "generation": user.get("generation", 0) + 1, "active": True},
        {"_id": 0},
    )
    if not user:
        raise HTTPException(401, "Sitzung wurde zwischenzeitlich widerrufen.")
    csrf = await new_session(user, response)
    await audit(user, "password.change")
    return {"user": public_user(user), "csrf": csrf, "locked": False}


class Account(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    display_name: str = Field(min_length=2, max_length=120)
    permissions: list[str] = []
    eligible: list[str] = []
    admin: bool = False


@router.get("/users")
async def users(request: Request):
    user = await identity(request)
    require(user, "users.manage")
    return [public_user(u) for u in await db.users.find({}, {"_id": 0}).to_list(10000)]


@router.post("/users", status_code=201)
async def create_user(payload: Account, request: Request):
    actor = await identity(request)
    require(actor, "users.manage")
    if not actor.get("admin"):
        raise HTTPException(
            403, "Nur Administratoren vergeben globale Rechte und Eignungen."
        )
    if set(payload.permissions) - PERMISSIONS or set(payload.eligible) - (
        ROLES - {"Helfer"}
    ):
        raise HTTPException(422, "Unbekanntes Recht oder unbekannte Eignung.")
    if payload.admin and "users.manage" not in payload.permissions:
        raise HTTPException(422, "Administratorkonto benötigt users.manage.")
    value = secrets.token_urlsafe(18)
    doc = {
        **payload.model_dump(),
        "id": str(uuid.uuid4()),
        "username": payload.username.lower(),
        "active": True,
        "generation": 0,
        "must_change_password": True,
        "password_hash": await password_hash(value),
    }
    recovery = secrets.token_urlsafe(32) if payload.admin else None
    if recovery:
        doc["recovery_hash"] = await password_hash(recovery)
    from pymongo.errors import DuplicateKeyError

    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Benutzername bereits vergeben.") from None
    await audit(
        actor,
        "user.create",
        data={
            "target_id": doc["id"],
            "permissions": doc["permissions"],
            "eligible": doc["eligible"],
        },
    )
    return {
        "user": public_user(doc),
        "initial_password": value,
        "recovery_code": recovery,
    }


@router.post("/users/{user_id}/reset")
async def reset(user_id: str, request: Request):
    actor = await identity(request)
    require(actor, "users.manage")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "Konto fehlt.")
    if target.get("admin") and not actor.get("admin"):
        raise HTTPException(403, "Administrator erforderlich.")
    value = secrets.token_urlsafe(18)
    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "password_hash": await password_hash(value),
                "must_change_password": True,
            },
            "$inc": {"generation": 1},
        },
    )
    await db.auth_sessions.delete_many({"user_id": user_id})
    await audit(actor, "user.password.reset", data={"target_id": user_id})
    return {"initial_password": value}


class AccountChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=2, max_length=120)
    permissions: list[str]
    eligible: list[str]


@router.put("/users/{user_id}")
async def change_account(user_id: str, payload: AccountChange, request: Request):
    actor = await identity(request)
    require(actor, "users.manage")
    if not actor.get("admin"):
        raise HTTPException(403, "Administrator erforderlich.")
    if set(payload.permissions) - PERMISSIONS or set(payload.eligible) - (
        ROLES - {"Helfer"}
    ):
        raise HTTPException(422, "Unbekannte Rechte/Eignungen.")
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Konto fehlt.")
    if target.get("admin") and "users.manage" not in payload.permissions:
        raise HTTPException(422, "Administratorkonto benötigt users.manage.")
    active_roles = await db.incidents.find(
        {
            "status": {"$ne": "abgeschlossen"},
            f"assignments.{user_id}.role": {"$exists": True},
        },
        {"_id": 0, "assignments": 1},
    ).to_list(None)
    needed = {i["assignments"][user_id]["role"] for i in active_roles} - {"Helfer"}
    if needed - set(payload.eligible):
        raise HTTPException(409, "Aktive Einsatzrolle vorher übergeben/aufheben.")
    await audit(
        actor,
        "user.permissions.change",
        data={
            "target_id": user_id,
            "before": public_user(target),
            "after": payload.model_dump(),
        },
    )
    await db.users.update_one(
        {"id": user_id}, {"$set": payload.model_dump(), "$inc": {"generation": 1}}
    )
    await db.auth_sessions.delete_many({"user_id": user_id})
    return {"ok": True}


class Deactivate(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
    emergency: bool = False

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Begründung erforderlich.")
        return value.strip()


@router.post("/users/{user_id}/activate")
async def activate(user_id: str, payload: Deactivate, request: Request):
    actor = await identity(request)
    require(actor, "users.manage")
    if not actor.get("admin"):
        raise HTTPException(403, "Administrator erforderlich.")
    target = await db.users.find_one({"id": user_id, "active": False})
    if not target:
        raise HTTPException(404, "Deaktiviertes Konto fehlt.")
    # Re-enabling an account must never reactivate its former operational roles.
    occupied = await db.incidents.find_one(
        {
            "status": {"$ne": "abgeschlossen"},
            f"assignments.{user_id}": {"$exists": True},
        }
    )
    if occupied:
        raise HTTPException(409, "Verbliebene Einsatzrollen zuerst übergeben/aufheben.")
    await audit(
        actor, "user.activate", reason=payload.reason, data={"target_id": user_id}
    )
    await db.users.update_one(
        {"id": user_id, "active": False},
        {"$set": {"active": True}, "$inc": {"generation": 1}},
    )
    return {"active": True}


@router.post("/users/{user_id}/deactivate")
async def deactivate(user_id: str, payload: Deactivate, request: Request):
    actor = await identity(request)
    require(actor, "users.manage")
    # Fail-closed distributed mutex. A crash leaves administration blocked until
    # an operator diagnoses and removes the lock, rather than risking last-admin loss.
    from pymongo.errors import DuplicateKeyError

    try:
        await db.identity_locks.insert_one({"_id": "deactivate"})
    except DuplicateKeyError:
        raise HTTPException(
            409,
            "Kontoverwaltung wird bearbeitet; bei anhaltender Sperre Betreiber kontaktieren.",
        ) from None
    try:
        target = await db.users.find_one({"id": user_id, "active": True})
        if not target:
            raise HTTPException(404, "Aktives Konto fehlt.")
        if target.get("admin"):
            if not actor.get("admin"):
                raise HTTPException(403, "Administrator erforderlich.")
            if await db.users.count_documents({"active": True, "admin": True}) <= 1:
                raise HTTPException(409, "Letzter aktiver Administrator bleibt aktiv.")
        incidents = await db.incidents.find(
            {
                "status": {"$ne": "abgeschlossen"},
                f"assignments.{user_id}": {"$exists": True},
            },
            {"_id": 0},
        ).to_list(None)
        leadership = [
            i["id"]
            for i in incidents
            if i["assignments"][user_id]["role"] in {"EL", "AL", "FueAss"}
        ]
        if leadership and not payload.emergency:
            raise HTTPException(
                409,
                {
                    "message": "Führungsfunktion vorher übergeben/aufheben.",
                    "incidents": leadership,
                },
            )
        await audit(
            actor,
            "user.emergency.disable" if payload.emergency else "user.disable",
            reason=payload.reason,
            data={"target_id": user_id, "pending_handover": leadership},
        )
        await db.users.update_one(
            {"id": user_id},
            {
                "$set": {"active": False, "pending_handover": leadership},
                "$inc": {"generation": 1},
            },
        )
        await db.auth_sessions.delete_many({"user_id": user_id})
        return {"disabled": True, "pending_handover": leadership}
    finally:
        await db.identity_locks.delete_one({"_id": "deactivate"})
