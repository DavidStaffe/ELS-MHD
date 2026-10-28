"""Divera 24/7 integration endpoints."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, SecretStr, StrictInt
from core.admin import admin_operation
from services import divera_settings, divera_polling

from core.db import db
from services import divera

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["divera"])


class KeyInput(BaseModel):
    api_key: SecretStr


class IntervalInput(BaseModel):
    interval: StrictInt


@router.get("/divera/settings")
async def settings_status():
    info = await divera_settings.public_settings()
    poll = await divera_polling.state()
    return {
        **info,
        **{
            k: poll.get(k)
            for k in (
                "last_attempt_at",
                "last_success_at",
                "error",
                "next_at",
                "failures",
            )
        },
    }


async def validate_key(key):
    if not key or len(key) > 1024 or any(c.isspace() for c in key):
        raise HTTPException(422, "Bitte einen gültigen API-Key eingeben.")
    try:
        return await divera.fetch_vehicles(api_key=key)
    except Exception as exc:
        import httpx

        invalid = isinstance(
            exc, httpx.HTTPStatusError
        ) and exc.response.status_code in (401, 403)
        raise HTTPException(
            422 if invalid else 502, divera_polling.safe_error(exc)
        ) from None


@router.post("/divera/settings/test", dependencies=[Depends(admin_operation)])
async def test_key(payload: KeyInput):
    try:
        async with divera_polling.operation():
            vehicles = await validate_key(payload.api_key.get_secret_value())
            return {"ok": True, "vehicles_total": len(vehicles)}
    except divera_polling.BusyError:
        raise HTTPException(
            409, "DIVERA-Abfrage läuft bereits. Erneut versuchen."
        ) from None


@router.put("/divera/settings/key", dependencies=[Depends(admin_operation)])
async def replace_key(payload: KeyInput):
    try:
        async with divera_polling.operation():
            # Always retest the exact submitted key on the server. A client-side
            # success flag is never sufficient authorization to replace it.
            divera_settings.cipher()
            key = payload.api_key.get_secret_value()
            await validate_key(key)
            await divera_settings.save(key=key)
            await divera_polling.invalidate()
    except divera_polling.BusyError:
        raise HTTPException(
            409, "DIVERA-Abfrage läuft bereits. Erneut versuchen."
        ) from None
    except ValueError:
        raise HTTPException(
            503, "Konfigurationsverschlüsselung ist nicht eingerichtet."
        ) from None
    return await divera_settings.public_settings()


@router.put("/divera/settings/interval", dependencies=[Depends(admin_operation)])
async def change_interval(payload: IntervalInput):
    try:
        async with divera_polling.operation():
            await divera_settings.save(interval=payload.interval)
            await divera_polling.invalidate()
    except divera_polling.BusyError:
        raise HTTPException(
            409, "DIVERA-Abfrage läuft bereits. Erneut versuchen."
        ) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return await divera_settings.public_settings()


@router.get("/divera/configured", response_model=Dict[str, Any])
async def divera_configured():
    """Whether Divera-API-Key is set up server-side."""
    return {
        "configured": (await divera_settings.public_settings())["configured"],
        "poll_interval_seconds": (await divera_settings.settings()).get("interval", 30),
    }


@router.get("/divera/vehicles", response_model=List[Dict[str, Any]])
async def divera_vehicles():
    """Live list of all Divera vehicles (for mapping UI)."""
    if not (await divera_settings.public_settings())["configured"]:
        raise HTTPException(status_code=503, detail="Divera nicht konfiguriert")
    try:
        return await divera_polling.vehicles()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=divera_polling.safe_error(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail="DIVERA derzeit nicht verfügbar.")


@router.get("/incidents/{incident_id}/divera/vehicles")
async def incident_divera_vehicles(incident_id: str):
    return await divera_vehicles()


@router.get("/incidents/{incident_id}/divera/status", response_model=Dict[str, Any])
async def divera_status(incident_id: str):
    inc = await db.incidents.find_one(
        {"id": incident_id},
        {
            "_id": 0,
            "divera_enabled": 1,
            "divera_last_poll_at": 1,
            "divera_last_poll_status": 1,
            "divera_last_match_count": 1,
            "status": 1,
        },
    )
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    linked_count = await db.resources.count_documents(
        {"incident_id": incident_id, "divera_id": {"$nin": [None, ""]}}
    )
    return {
        "configured": (await divera_settings.public_settings())["configured"],
        "running": bool(inc.get("divera_enabled"))
        and inc.get("status") != "abgeschlossen",
        "enabled": bool(inc.get("divera_enabled")),
        "last_poll_at": inc.get("divera_last_poll_at"),
        "last_status": inc.get("divera_last_poll_status"),
        "last_match_count": inc.get("divera_last_match_count"),
        "linked_resources": linked_count,
        "poll_interval_seconds": (await divera_settings.settings()).get("interval", 30),
        "incident_status": inc.get("status"),
    }


@router.post("/incidents/{incident_id}/divera/start", response_model=Dict[str, Any])
async def divera_start(incident_id: str):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0, "status": 1})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    if inc.get("status") == "abgeschlossen":
        raise HTTPException(
            status_code=409,
            detail="Polling fuer archivierten Incident nicht moeglich",
        )
    try:
        await divera_polling.start_polling(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    # Trigger one immediate sync so the user sees fresh data right away
    result = await divera_polling.sync_incident(incident_id)
    return {"running": True, "enabled": True, "first_sync": result}


@router.post("/incidents/{incident_id}/divera/stop", response_model=Dict[str, Any])
async def divera_stop(incident_id: str):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    await divera_polling.stop_polling(incident_id)
    return {"running": False}


@router.post("/incidents/{incident_id}/divera/sync", response_model=Dict[str, Any])
async def divera_sync_now(incident_id: str):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    if inc.get("status") == "abgeschlossen":
        raise HTTPException(
            409, "Synchronisierung für archivierten Incident nicht möglich."
        )
    if not (await divera_settings.public_settings())["configured"]:
        raise HTTPException(status_code=503, detail="Divera nicht konfiguriert")
    return await divera_polling.sync_incident(incident_id)
