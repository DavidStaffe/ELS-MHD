"""Installation-wide, encrypted DIVERA configuration.

A Fernet key and a separate admin password are provisioned once by the operator.
Never return stored credentials through an API response or log them.
"""
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Header

from core.db import db
from core.time import iso, now_utc

ALLOWED_INTERVALS = (5, 10, 20, 30, 60, 120, 300)
DOCUMENT_ID = "divera"
DEFAULT_INTERVAL = int(os.environ.get("DIVERA_POLL_INTERVAL_SECONDS", "30"))
if DEFAULT_INTERVAL not in ALLOWED_INTERVALS:
    DEFAULT_INTERVAL = 30


def require_admin(x_els_admin_password: str = Header(default="", alias="X-ELS-Admin-Password")) -> None:
    """Temporary independent admin credential until authenticated users exist."""
    configured = os.environ.get("ELS_ADMIN_PASSWORD", "")
    if not configured:
        raise HTTPException(503, "Administrator-Passwort ist noch nicht eingerichtet")
    if not hmac.compare_digest(x_els_admin_password.encode(), configured.encode()):
        raise HTTPException(403, "Administrator-Passwort ungültig")


def _cipher() -> Fernet:
    secret = os.environ.get("ELS_SETTINGS_ENCRYPTION_KEY", "")
    if not secret:
        raise HTTPException(503, "ELS_SETTINGS_ENCRYPTION_KEY muss einmalig eingerichtet werden")
    try:
        return Fernet(secret.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "ELS_SETTINGS_ENCRYPTION_KEY ist ungültig")


async def get_config() -> dict:
    doc = await db.global_settings.find_one({"_id": DOCUMENT_ID})
    key = os.environ.get("DIVERA_API_KEY", "")
    interval = DEFAULT_INTERVAL
    if doc:
        interval = doc.get("interval_seconds", interval)
        encrypted = doc.get("api_key_encrypted")
        if encrypted:
            try:
                key = _cipher().decrypt(encrypted.encode()).decode()
            except (InvalidToken, UnicodeDecodeError):
                raise HTTPException(503, "Gespeicherter DIVERA-Key kann nicht entschlüsselt werden")
    return {"api_key": key, "interval_seconds": interval}


async def public_config() -> dict:
    config = await get_config()
    return {"configured": bool(config["api_key"]),
            "poll_interval_seconds": config["interval_seconds"]}


async def save_config(*, api_key: str | None = None, interval_seconds: int | None = None) -> dict:
    changes = {"updated_at": iso(now_utc())}
    if interval_seconds is not None:
        if interval_seconds not in ALLOWED_INTERVALS:
            raise HTTPException(422, "Unzulässiges Abrufintervall")
        changes["interval_seconds"] = interval_seconds
    if api_key is not None:
        if not api_key.strip():
            raise HTTPException(422, "API-Key darf nicht leer sein")
        changes["api_key_encrypted"] = _cipher().encrypt(api_key.strip().encode()).decode()
    if len(changes) < 2:
        raise HTTPException(400, "Keine Änderung angegeben")
    await db.global_settings.update_one(
        {"_id": DOCUMENT_ID}, {"$set": changes}, upsert=True
    )
    return await public_config()
