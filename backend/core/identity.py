"""Server-owned identities. No browser role, name or bearer claim is trusted."""

import hashlib
import hmac
import secrets
import time
import asyncio
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException, Request
from pymongo import ReturnDocument

from core.db import db
from core.time import now_utc, iso

COOKIE = "__Host-els-session"
IDLE_SECONDS = 600
PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
_password_slots = asyncio.Semaphore(2)
PERMISSIONS = frozenset(
    {
        "users.manage",
        "settings.manage",
        "incidents.create",
        "incidents.roles.assign",
        "incidents.all.read",
        "incidents.close",
        "incidents.reopen",
        "archives.manage",
        "archives.correct",
        "archives.patients.correct",
        "patients.read",
        "helpers.patients.create",
        "helpers.patients.update",
    }
)
ROLES = frozenset({"EL", "FueAss", "AL", "Dokumentar", "Helfer"})


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def verify(password, encoded):
    try:
        return PASSWORDS.verify(encoded, password)
    except (VerificationError, InvalidHashError, TypeError):
        return False


async def password_hash(value):
    async with _password_slots:
        return await asyncio.to_thread(PASSWORDS.hash, value)


async def password_verify(value, encoded):
    async with _password_slots:
        return await asyncio.to_thread(verify, value, encoded)


async def audit(actor, action, *, incident_id=None, reason=None, data=None):
    await db.security_audit.insert_one(
        {
            "at": iso(now_utc()),
            "user_id": actor.get("id"),
            "username": actor.get("username"),
            "display_name": actor.get("display_name"),
            "action": action,
            "incident_id": incident_id,
            "reason": reason,
            "data": data,
        }
    )


def has(user, permission):
    # Administration is deliberately not a wildcard.
    return permission in PERMISSIONS and permission in user.get("permissions", [])


def require(user, permission):
    if not has(user, permission):
        raise HTTPException(403, "Berechtigung fehlt.")


async def limit(key, maximum=5, seconds=300):
    bucket = int(time.time()) // seconds
    result = await db.auth_limits.find_one_and_update(
        {"_id": f"{key}:{bucket}"},
        {
            "$inc": {"attempts": 1},
            "$setOnInsert": {"expires_at": now_utc() + timedelta(seconds=seconds * 2)},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if result["attempts"] > maximum:
        raise HTTPException(429, "Zu viele Versuche. Bitte später erneut versuchen.")


async def identity(request: Request, *, allow_locked=False, allow_change=False):
    token = request.cookies.get(COOKIE, "")
    session = (
        await db.auth_sessions.find_one(
            {"_id": digest(token), "expires_at": {"$gt": iso(now_utc())}}
        )
        if token
        else None
    )
    user = (
        await db.users.find_one({"id": session["user_id"], "active": True}, {"_id": 0})
        if session
        else None
    )
    if not user or session.get("generation") != user.get("generation", 0):
        raise HTTPException(401, "Anmeldung erforderlich.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not hmac.compare_digest(
            request.headers.get("X-CSRF-Token", ""), session["csrf"]
        ):
            raise HTTPException(403, "CSRF-Prüfung fehlgeschlagen.")
    locked = (
        session.get("locked", False)
        or time.time() - session["activity"] >= IDLE_SECONDS
    )
    if locked and not allow_locked:
        raise HTTPException(423, "Arbeitsplatz gesperrt.")
    if user.get("must_change_password") and not allow_change:
        raise HTTPException(428, "Passwortwechsel erforderlich.")
    request.state.user = user
    request.state.session = session
    request.state.locked = locked
    return user


async def new_session(user, response):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    await db.auth_sessions.insert_one(
        {
            "_id": digest(token),
            "user_id": user["id"],
            "generation": user.get("generation", 0),
            "csrf": csrf,
            "activity": time.time(),
            "locked": False,
            "expires_at": iso(now_utc() + timedelta(hours=12)),
        }
    )
    response.set_cookie(
        COOKIE,
        token,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
        max_age=43200,
    )
    response.headers["Cache-Control"] = "no-store"
    return csrf


def public_user(user):
    return {
        key: user.get(key)
        for key in (
            "id",
            "username",
            "display_name",
            "active",
            "admin",
            "permissions",
            "eligible",
            "must_change_password",
        )
    }


async def indexes():
    await db.users.create_index("id", unique=True)
    await db.users.create_index("username", unique=True)
    await db.auth_limits.create_index("expires_at", expireAfterSeconds=0)


async def incident_access(user, incident):
    if incident.get("created_by") == user["id"] or has(user, "incidents.all.read"):
        return True
    if incident.get("status") == "abgeschlossen":
        grant = await db.archive_grants.find_one(
            {
                "incident_id": incident["id"],
                "user_id": user["id"],
                "revoked": False,
                "expires_at": {"$gt": iso(now_utc())},
            }
        )
        return bool(grant)
    return user["id"] in incident.get("assignments", {})


def present_incident(user, incident):
    # Closure snapshots and historical assignments are not general situation data.
    hidden = {
        "security_history",
        "closure_open_snapshot",
        "inactive_assignments",
        "_id",
    }
    result = {k: v for k, v in incident.items() if k not in hidden}
    result["can_close"] = incident.get("status") != "abgeschlossen" and (
        has(user, "incidents.close") or role_for(user, incident).get("role") == "EL"
    )
    result["can_reopen"] = incident.get("status") == "abgeschlossen" and (
        has(user, "incidents.reopen")
        or (
            incident.get("closed_personally_as_el")
            and incident.get("closed_by") == user["id"] == incident.get("last_el_id")
        )
    )
    if (
        role_for(user, incident).get("role") == "Helfer"
        and incident.get("created_by") != user["id"]
    ):
        result = {k: incident.get(k) for k in ("id", "name", "status")}
        result["assignments"] = {user["id"]: role_for(user, incident)}
    return result


def role_for(user, incident):
    if incident.get("status") == "abgeschlossen":
        return {}
    return incident.get("assignments", {}).get(user["id"], {})


def medical(user, incident):
    return (
        role_for(user, incident).get("role") in {"EL", "FueAss", "AL"}
        or has(user, "patients.read")
        or incident.get("created_by") == user["id"]
    )


async def stream_authorized(request, incident_id=None):
    """Recheck every emission; an open stream is never a lasting access grant."""
    try:
        user = await identity(request)
        if incident_id:
            inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
            return bool(inc and await incident_access(user, inc) and medical(user, inc))
        return True
    except HTTPException:
        return False
