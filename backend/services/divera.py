"""Divera 24/7 integration: pull vehicle FMS status, sync to ELS resources.

Provides:
- fetch_vehicles(): pull current vehicle list from Divera
- sync_incident(): match Divera vehicles to ELS resources via divera_id, update
                   resource status + fms_status + lat/lng (if linked)
- start_polling(incident_id): start background task polling every 30s
- stop_polling(incident_id): stop running task

Key configuration via env:
- DIVERA_API_KEY         (required)
- DIVERA_BASE_URL        (default https://www.divera247.com)
- DIVERA_POLL_INTERVAL_SECONDS (default 30)
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from core.db import db
from core.time import iso, now_utc
from services.realtime import publish_incident_event
from services.fms_audit import record_fms_change

logger = logging.getLogger(__name__)

DIVERA_BASE_URL = os.environ.get("DIVERA_BASE_URL", "https://www.divera247.com")
DIVERA_API_KEY = os.environ.get("DIVERA_API_KEY", "")
POLL_INTERVAL = int(os.environ.get("DIVERA_POLL_INTERVAL_SECONDS", "30"))

# FMS-Status -> ELS-Resource-Status mapping
# BOS standard: 1/2 = available, 3/4/7/8 = in_einsatz, 5/0 = sprechwunsch, 6 = offline, 9 = wartung
_FMS_TO_RESOURCE_STATUS = {
    0: None,            # priorisierter Sprechwunsch - keep existing
    1: "verfuegbar",
    2: "verfuegbar",
    3: "im_einsatz",
    4: "im_einsatz",
    5: None,            # Sprechwunsch - keep existing
    6: "offline",
    7: "im_einsatz",
    8: "im_einsatz",
    9: "offline",       # Wartung
}

# Registry of running polling tasks
_running_tasks: Dict[str, asyncio.Task] = {}


def _is_configured() -> bool:
    return bool(DIVERA_API_KEY)


async def fetch_vehicles(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch all vehicles + FMS status from Divera. Returns list of dicts.

    Raises httpx.HTTPError on network errors, ValueError on API errors.
    """
    key = api_key or DIVERA_API_KEY
    if not key:
        raise ValueError("DIVERA_API_KEY ist nicht konfiguriert")
    url = f"{DIVERA_BASE_URL}/api/v2/pull/vehicle-status"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params={"accesskey": key})
        resp.raise_for_status()
        data = resp.json()
    if not data.get("success"):
        raise ValueError(f"Divera API error: {data.get('message', 'unknown')}")
    return data.get("data") or []


async def sync_incident(incident_id: str) -> Dict[str, Any]:
    """Pull vehicles + update linked resources for given incident.

    Returns a result dict: { ok, matched, vehicles_total, timestamp, error? }.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "matched": 0,
        "vehicles_total": 0,
        "timestamp": iso(now_utc()),
    }
    try:
        vehicles = await fetch_vehicles()
        result["vehicles_total"] = len(vehicles)
    except httpx.HTTPError as exc:
        result["error"] = f"HTTP-Fehler: {exc}"
        await _record_poll_result(incident_id, "error", str(exc)[:200], 0)
        return result
    except ValueError as exc:
        result["error"] = str(exc)
        await _record_poll_result(incident_id, "error", str(exc)[:200], 0)
        return result

    by_id: Dict[str, Dict[str, Any]] = {str(v["id"]): v for v in vehicles}

    linked = await db.resources.find(
        {"incident_id": incident_id, "divera_id": {"$nin": [None, ""]}},
        {"_id": 0},
    ).to_list(500)

    matched = 0
    now = now_utc()
    for resource in linked:
        v = by_id.get(str(resource.get("divera_id")))
        if not v:
            continue
        fms = v.get("fmsstatus") if v.get("fmsstatus") is not None else v.get("fmsstatus_id")
        old_fms = resource.get("fms_status")
        old_status = resource.get("status")
        new_status = old_status
        update: Dict[str, Any] = {
            "fms_status": fms,
            "updated_at": iso(now),
        }
        if fms in _FMS_TO_RESOURCE_STATUS and _FMS_TO_RESOURCE_STATUS[fms]:
            new_status = _FMS_TO_RESOURCE_STATUS[fms]
            update["status"] = new_status
        # Live-Tracking: wenn Divera lat/lng liefert, IMMER auf Resource synchronisieren
        # (sonst wuerde der Standort eines Fahrzeugs niemals automatisch updaten).
        try:
            d_lat = v.get("lat")
            d_lng = v.get("lng")
            if d_lat is not None and d_lng is not None:
                d_lat = float(d_lat)
                d_lng = float(d_lng)
                # Plausibilitaetscheck: 0/0 ist meist "kein Fix"
                if abs(d_lat) > 0.01 or abs(d_lng) > 0.01:
                    if d_lat != resource.get("lat") or d_lng != resource.get("lng"):
                        update["lat"] = d_lat
                        update["lng"] = d_lng
        except (TypeError, ValueError):
            pass
        await db.resources.update_one({"id": resource["id"]}, {"$set": update})
        # FMS-Audit nur bei tatsaechlicher Aenderung
        if old_fms != fms:
            await record_fms_change(
                incident_id=incident_id,
                resource_id=resource["id"],
                resource_name=resource.get("name", ""),
                vehicle_name=v.get("name"),
                divera_id=str(v.get("id")),
                from_fms=old_fms,
                to_fms=fms,
                from_status=old_status,
                to_status=new_status,
                source="divera",
            )
        matched += 1

    await _record_poll_result(incident_id, "ok", None, matched)
    await publish_incident_event(
        {
            "kind": "resource",
            "action": "synced",
            "incident_id": incident_id,
            "count": matched,
            "ts": iso(now_utc()),
        }
    )

    result["ok"] = True
    result["matched"] = matched
    return result


async def _record_poll_result(
    incident_id: str, status: str, message: Optional[str], matched: int
) -> None:
    await db.incidents.update_one(
        {"id": incident_id},
        {
            "$set": {
                "divera_last_poll_at": iso(now_utc()),
                "divera_last_poll_status": (
                    "ok" if status == "ok" else f"error: {message}"
                ),
                "divera_last_match_count": matched,
                "updated_at": iso(now_utc()),
            }
        },
    )


async def start_polling(incident_id: str) -> None:
    """Start a background polling task for incident_id."""
    if not _is_configured():
        raise ValueError("DIVERA_API_KEY nicht konfiguriert")
    if incident_id in _running_tasks and not _running_tasks[incident_id].done():
        return  # already running

    async def loop() -> None:
        logger.info("Divera-Polling gestartet fuer %s (interval=%ss)", incident_id, POLL_INTERVAL)
        try:
            while True:
                # Verify incident still wants polling
                inc = await db.incidents.find_one(
                    {"id": incident_id}, {"_id": 0, "status": 1, "divera_enabled": 1}
                )
                if not inc or not inc.get("divera_enabled") or inc.get("status") == "abgeschlossen":
                    logger.info("Divera-Polling fuer %s gestoppt (state changed)", incident_id)
                    break
                try:
                    await sync_incident(incident_id)
                except Exception as exc:  # pragma: no cover
                    logger.exception("Divera-Sync fehlgeschlagen: %s", exc)
                await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            logger.info("Divera-Polling fuer %s cancelled", incident_id)
            raise
        finally:
            _running_tasks.pop(incident_id, None)

    task = asyncio.create_task(loop())
    _running_tasks[incident_id] = task
    await db.incidents.update_one(
        {"id": incident_id}, {"$set": {"divera_enabled": True, "updated_at": iso(now_utc())}}
    )


async def stop_polling(incident_id: str) -> None:
    """Stop background polling for incident_id and mark divera_enabled=False."""
    task = _running_tasks.get(incident_id)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _running_tasks.pop(incident_id, None)
    await db.incidents.update_one(
        {"id": incident_id}, {"$set": {"divera_enabled": False, "updated_at": iso(now_utc())}}
    )


def is_polling(incident_id: str) -> bool:
    task = _running_tasks.get(incident_id)
    return task is not None and not task.done()


async def resume_active_pollings() -> None:
    """Re-start polling tasks for incidents that were enabled before a restart."""
    if not _is_configured():
        return
    async for inc in db.incidents.find(
        {"divera_enabled": True, "status": {"$ne": "abgeschlossen"}},
        {"_id": 0, "id": 1},
    ):
        try:
            await start_polling(inc["id"])
        except Exception as exc:  # pragma: no cover
            logger.warning("Konnte Divera-Polling fuer %s nicht resumen: %s", inc["id"], exc)
