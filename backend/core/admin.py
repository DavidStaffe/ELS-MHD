"""Installation administrator authentication, independent of client-selected roles.

Opaque bearer tokens stay in browser memory. Only their digests are persisted.
Use TLS (or a local SSH tunnel); never publish management over plain HTTP.
"""

import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, SecretStr

from core.db import db
from core.time import now_utc, iso

router = APIRouter(prefix="/api/admin", tags=["admin"])
bearer = HTTPBearer(auto_error=False)


async def audit(action, outcome):
    await db.admin_audit.insert_one(
        {
            "action": action,
            "outcome": outcome,
            "actor": "installation-admin",
            "at": iso(now_utc()),
        }
    )


def secret_setting(name):
    path = os.environ.get(name + "_FILE")
    return (
        Path(path).read_text(encoding="utf-8").strip()
        if path
        else os.environ.get(name, "")
    )


def password_matches(password, encoded):
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        )
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


class Login(BaseModel):
    password: SecretStr


@router.post("/login")
async def login(payload: Login):
    try:
        encoded = secret_setting("ELS_ADMIN_PASSWORD_HASH")
    except OSError:
        encoded = ""
    if not encoded:
        raise HTTPException(503, "Administratorzugang ist nicht eingerichtet.")
    now = now_utc()
    # A global, database-backed fixed-window limiter also applies across workers.
    await db.admin_limits.update_one(
        {
            "_id": "login",
            "$or": [{"until": {"$lte": iso(now)}}, {"until": {"$exists": False}}],
        },
        {"$set": {"attempts": 0, "until": iso(now + timedelta(minutes=5))}},
    )
    from pymongo.errors import DuplicateKeyError

    try:
        await db.admin_limits.update_one(
            {"_id": "login"},
            {"$setOnInsert": {"attempts": 0, "until": iso(now + timedelta(minutes=5))}},
            upsert=True,
        )
    except DuplicateKeyError:
        pass
    allowed = await db.admin_limits.update_one(
        {"_id": "login", "attempts": {"$lt": 5}}, {"$inc": {"attempts": 1}}
    )
    if not allowed.modified_count:
        raise HTTPException(
            429, "Zu viele Anmeldeversuche. Nach fünf Minuten erneut versuchen."
        )
    password = payload.password.get_secret_value()
    if len(password) > 1024 or not password_matches(password, encoded):
        await audit("login", "denied")
        raise HTTPException(401, "Administratoranmeldung fehlgeschlagen.")
    token = secrets.token_urlsafe(32)
    await db.admin_sessions.delete_many({"expires_at": {"$lte": iso(now)}})
    await db.admin_sessions.insert_one(
        {
            "_id": hashlib.sha256(token.encode()).hexdigest(),
            "expires_at": iso(now + timedelta(minutes=10)),
        }
    )
    await audit("login", "succeeded")
    return {"token": token, "expires_in": 600}


async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Administratoranmeldung erforderlich.")
    digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    session = await db.admin_sessions.find_one(
        {"_id": digest, "expires_at": {"$gt": iso(now_utc())}}
    )
    if not session:
        raise HTTPException(401, "Administratoranmeldung abgelaufen oder ungültig.")
    return digest


async def admin_operation(request: Request, actor=Depends(require_admin)):
    actions = {
        "/api/divera/settings/test": "divera.key.test",
        "/api/divera/settings/key": "divera.key.replace",
        "/api/divera/settings/interval": "divera.interval.change",
    }
    action = actions[request.url.path]
    await audit(action, "started")
    try:
        yield actor
    except Exception:
        await audit(action, "failed")
        raise
    else:
        await audit(action, "succeeded")


@router.post("/logout")
async def logout(digest=Depends(require_admin)):
    await db.admin_sessions.delete_one({"_id": digest})
    return {"ok": True}
