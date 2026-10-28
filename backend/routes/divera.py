"""Divera 24/7 integration endpoints."""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from services import divera_settings

from core.db import db
from services import divera

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["divera"])


@router.get("/divera/configured", response_model=Dict[str, Any])
async def divera_configured():
    """Whether Divera-API-Key is set up server-side."""
    return {
        "configured": (await divera_settings.public_config())["configured"],
        "poll_interval_seconds": (await divera_settings.public_config())["poll_interval_seconds"],
    }


@router.get("/divera/vehicles", response_model=List[Dict[str, Any]])
async def divera_vehicles():
    """Live list of all Divera vehicles (for mapping UI)."""
    if not (await divera_settings.public_config())["configured"]:
        raise HTTPException(status_code=503, detail="Divera nicht konfiguriert")
    try:
        return await divera.fetch_vehicles_cached()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Divera-Fehler: {exc}")


@router.get("/incidents/{incident_id}/divera/status", response_model=Dict[str, Any])
async def divera_status(incident_id: str):
    inc = await db.incidents.find_one(
        {"id": incident_id},
        {"_id": 0, "divera_enabled": 1, "divera_last_poll_at": 1,
         "divera_last_poll_status": 1, "divera_last_match_count": 1, "status": 1},
    )
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    linked_count = await db.resources.count_documents(
        {"incident_id": incident_id, "divera_id": {"$nin": [None, ""]}}
    )
    return {
        "configured": bool(divera.DIVERA_API_KEY),
        "running": bool(inc.get("divera_enabled")) and divera.is_polling(incident_id),
        "enabled": bool(inc.get("divera_enabled")),
        "last_poll_at": inc.get("divera_last_poll_at"),
        "last_status": inc.get("divera_last_poll_status"),
        "last_match_count": inc.get("divera_last_match_count"),
        "linked_resources": linked_count,
        "poll_interval_seconds": divera.POLL_INTERVAL,
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
        await divera.start_polling(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    # Central loop fetches for every enabled incident; no duplicate first fetch.
    result = {"ok": True, "pending": True}
    return {"running": True, "first_sync": result}


@router.post("/incidents/{incident_id}/divera/stop", response_model=Dict[str, Any])
async def divera_stop(incident_id: str):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    await divera.stop_polling(incident_id)
    return {"running": False}


@router.post("/incidents/{incident_id}/divera/sync", response_model=Dict[str, Any])
async def divera_sync_now(incident_id: str):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    if not divera.DIVERA_API_KEY:
        raise HTTPException(status_code=503, detail="Divera nicht konfiguriert")
    return await divera.sync_including(incident_id)


class DiveraSettingsUpdate(BaseModel):
    api_key: Optional[str] = Field(default=None, min_length=1, max_length=1024)
    interval_seconds: Optional[int] = None


class DiveraKeyTest(BaseModel):
    api_key: str = Field(min_length=1, max_length=1024)


@router.get("/settings/divera", dependencies=[Depends(divera_settings.require_admin)])
async def get_divera_settings():
    return await divera_settings.public_config()


@router.post("/settings/divera/test", dependencies=[Depends(divera_settings.require_admin)])
async def test_divera_key(payload: DiveraKeyTest):
    try:
        vehicles = await divera.fetch_vehicles(api_key=payload.api_key)
        return {"ok": True, "vehicles_total": len(vehicles)}
    except Exception:
        raise HTTPException(422, "DIVERA-Verbindungstest fehlgeschlagen; Key oder Netzwerk prüfen")


@router.patch("/settings/divera", dependencies=[Depends(divera_settings.require_admin)])
async def update_divera_settings(payload: DiveraSettingsUpdate):
    if payload.api_key is not None:
        try:
            await divera.fetch_vehicles(api_key=payload.api_key)
        except Exception:
            raise HTTPException(422, "Neuer API-Key konnte nicht erfolgreich geprüft werden")
    conf = await divera_settings.save_config(
        api_key=payload.api_key, interval_seconds=payload.interval_seconds
    )
    divera.settings_changed()
    await divera.resume_active_pollings()
    return conf
