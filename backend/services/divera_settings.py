"""Encrypted installation settings. Encryption key is held outside MongoDB."""

from cryptography.fernet import Fernet, InvalidToken
from core.admin import secret_setting
from core.db import db
from core.time import iso, now_utc

INTERVALS = (5, 10, 20, 30, 60, 120, 300)


def cipher():
    try:
        return Fernet(secret_setting("ELS_CONFIG_ENCRYPTION_KEY").encode())
    except (ValueError, OSError):
        raise ValueError(
            "Konfigurationsverschlüsselung ist nicht eingerichtet."
        ) from None


async def settings():
    current = await db.system_settings.find_one({"_id": "divera"})
    if current:
        return current
    legacy = await db.global_settings.find_one({"_id": "divera"})
    if legacy:
        # PR #6 used another collection and encryption-key setting. Read it
        # without overwriting or deleting the original rollback-compatible copy.
        return {"interval": legacy.get("interval_seconds", 30), "legacy_encrypted_key": legacy.get("api_key_encrypted")}
    return {"interval": 30}


async def current_key():
    config = await settings()
    if config.get("legacy_encrypted_key"):
        try:
            key = secret_setting("ELS_SETTINGS_ENCRYPTION_KEY")
            return Fernet(key.encode()).decrypt(config["legacy_encrypted_key"].encode()).decode()
        except (ValueError, InvalidToken, OSError, UnicodeDecodeError):
            raise ValueError("Alter DIVERA-Key nicht entschlüsselbar; Legacy-Verschlüsselung prüfen.") from None
    encrypted = config.get("encrypted_key")
    if encrypted:
        try:
            return cipher().decrypt(encrypted.encode()).decode()
        except InvalidToken:
            raise ValueError(
                "Gespeicherter DIVERA-Key kann nicht entschlüsselt werden."
            ) from None
    # Compatibility fallback until an administrator saves a replacement.
    return secret_setting("DIVERA_API_KEY")


async def initialize():
    # Idempotent migration: never overwrite a key set through the web interface.
    config = await settings()
    legacy = await current_key()
    if legacy:
        encrypted = cipher().encrypt(legacy.encode()).decode()
        await db.system_settings.update_one(
            {"_id": "divera"}, {"$setOnInsert": {"interval": config.get("interval", 30)}}, upsert=True
        )
        await db.system_settings.update_one(
            {"_id": "divera", "encrypted_key": {"$exists": False}},
            {"$set": {"encrypted_key": encrypted}},
        )


async def public_settings():
    config = await settings()
    try:
        configured = bool(await current_key())
        error = None
    except (ValueError, OSError):
        configured = False
        error = (
            "Gespeicherter Key nicht lesbar; Verschlüsselung prüfen oder Key ersetzen."
        )
    return {
        "configured": configured,
        "poll_interval_seconds": config.get("interval", 30),
        "intervals": INTERVALS,
        "five_seconds_allowed": False,
        "configuration_error": error,
        "key_verified_at": config.get("key_verified_at"),
    }


async def save(*, key=None, interval=None):
    changes = {}
    if interval is not None:
        if interval not in INTERVALS or interval == 5:
            raise ValueError(
                "Intervall unzulässig; 5 Sekunden sind bis zur DIVERA-Limitprüfung gesperrt."
            )
        changes["interval"] = interval
    if key is not None:
        changes.update(
            encrypted_key=cipher().encrypt(key.encode()).decode(),
            key_verified_at=iso(now_utc()),
        )
    await db.system_settings.update_one(
        {"_id": "divera"},
        {
            "$set": changes,
            "$setOnInsert": {} if interval is not None else {"interval": 30},
        },
        upsert=True,
    )
