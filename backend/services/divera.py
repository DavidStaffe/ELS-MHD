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
from services import divera_settings

logger = logging.getLogger(__name__)

DIVERA_BASE_URL = os.environ.get("DIVERA_BASE_URL", "https://www.divera247.com")
DIVERA_API_KEY = os.environ.get("DIVERA_API_KEY", "")  # legacy fallback only
POLL_INTERVAL = divera_settings.DEFAULT_INTERVAL

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
    key = api_key if api_key is not None else (await divera_settings.get_config())["api_key"]
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


async def set_vehicle_status(
    divera_id: str,
    status_id: int,
    status_note: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Setzt FMS-Status eines Fahrzeugs in Divera 24/7.

    Endpoint: GET https://divera247.com/api/fms
    Params:
      accesskey, vehicle_id, status_id [1-9], status_note (optional)

    Wird genutzt um nach Quittierung eines Sprechwunsches (FMS 5/0) den
    vorherigen FMS-Status wiederherzustellen UND gleichzeitig die Nachricht
    "SPRECHEN SIE" ueber status_note ans Fahrzeug zu schicken.

    Raises httpx.HTTPError on network errors, ValueError on API errors.
    """
    key = api_key or DIVERA_API_KEY
    if not key:
        raise ValueError("DIVERA_API_KEY ist nicht konfiguriert")
    if not divera_id:
        raise ValueError("divera_id fehlt")
    url = f"{DIVERA_BASE_URL}/api/fms"
    params: Dict[str, Any] = {
        "accesskey": key,
        "vehicle_id": divera_id,
        "status_id": status_id,
    }
    if status_note:
        params["status_note"] = status_note
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}
    # Divera kann success=true/false zurueckliefern
    if isinstance(data, dict) and data.get("success") is False:
        raise ValueError(f"Divera FMS API error: {data.get('message', 'unknown')}")
    return data if isinstance(data, dict) else {"raw": data}


async def sync_incident(incident_id: str, vehicles: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
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
        if vehicles is None:
            vehicles = await fetch_vehicles_cached()
        result["vehicles_total"] = len(vehicles)
    except httpx.HTTPError as exc:
        result["error"] = "DIVERA-Netzwerk- oder HTTP-Fehler"
        await _record_poll_result(incident_id, "error", result["error"], 0)
        return result
    except ValueError as exc:
        result["error"] = "DIVERA-Antwort oder API-Key ungültig"
        await _record_poll_result(incident_id, "error", result["error"], 0)
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
                    update["position_updated_at"] = iso(now)
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


# Single process coordinator; one fetch is fanned out to all enabled incidents.
_poll_task: Optional[asyncio.Task] = None
_poll_wakeup = asyncio.Event()
_fetch_lock = asyncio.Lock()
_sync_lock = asyncio.Lock()
_fetch_cache: Optional[List[Dict[str, Any]]] = None
_fetch_cache_at: float = 0.0
_last_error: Optional[str] = None


async def fetch_vehicles_cached(force: bool = False) -> List[Dict[str, Any]]:
    """One shared fetch; UI listings reuse the current snapshot."""
    global _fetch_cache, _fetch_cache_at
    async with _fetch_lock:
        conf = await divera_settings.get_config()
        ttl = max(5, conf["interval_seconds"])
        if not force and _fetch_cache is not None and asyncio.get_running_loop().time() - _fetch_cache_at < ttl:
            return _fetch_cache
        vehicles = await fetch_vehicles()
        _fetch_cache = vehicles
        _fetch_cache_at = asyncio.get_running_loop().time()
        return vehicles


def settings_changed() -> None:
    global _fetch_cache, _fetch_cache_at
    _fetch_cache = None
    _fetch_cache_at = 0
    _poll_wakeup.set()


async def _enabled_incidents() -> list[str]:
    docs = await db.incidents.find(
        {"divera_enabled": True, "status": {"$nin": ["abgeschlossen", "archiviert"]}},
        {"_id": 0, "id": 1},
    ).to_list(2000)
    return [d["id"] for d in docs]


async def sync_all(force: bool = True) -> dict:
    async with _sync_lock:
        return await _sync_all_locked(force)


async def _sync_all_locked(force: bool = True) -> dict:
    global _last_error
    ids = await _enabled_incidents()
    if not ids:
        return {"ok": True, "matched": 0, "vehicles_total": 0}
    try:
        vehicles = await fetch_vehicles_cached(force=force)
        _last_error = None
    except Exception:
        _last_error = "DIVERA-Abruf fehlgeschlagen"
        for incident_id in ids:
            await _record_poll_result(incident_id, "error", _last_error, 0)
        return {"ok": False, "error": _last_error, "matched": 0, "vehicles_total": 0}
    results = await asyncio.gather(
        *(sync_incident(incident_id, vehicles) for incident_id in ids),
        return_exceptions=True,
    )
    matched = sum(item.get("matched", 0) for item in results if isinstance(item, dict))
    return {"ok": all(isinstance(item, dict) and item.get("ok") for item in results),
            "matched": matched, "vehicles_total": len(vehicles)}


async def _central_loop() -> None:
    delay_multiplier = 1
    while True:
        ids = await _enabled_incidents()
        if not ids:
            return
        result = await sync_all()
        delay_multiplier = 1 if result["ok"] else min(delay_multiplier * 2, 12)
        interval = (await divera_settings.get_config())["interval_seconds"]
        try:
            await asyncio.wait_for(_poll_wakeup.wait(), timeout=interval * delay_multiplier)
        except asyncio.TimeoutError:
            pass
        _poll_wakeup.clear()


async def _ensure_task() -> None:
    global _poll_task
    if _poll_task is None or _poll_task.done():
        _poll_task = asyncio.create_task(_central_loop())


async def start_polling(incident_id: str) -> None:
    config = await divera_settings.get_config()
    if not config["api_key"]:
        raise ValueError("DIVERA API-Key nicht konfiguriert")
    await db.incidents.update_one(
        {"id": incident_id}, {"$set": {"divera_enabled": True, "updated_at": iso(now_utc())}}
    )
    await _ensure_task()


async def stop_polling(incident_id: str) -> None:
    await db.incidents.update_one(
        {"id": incident_id}, {"$set": {"divera_enabled": False, "updated_at": iso(now_utc())}}
    )
    _poll_wakeup.set()


def is_polling(incident_id: str) -> bool:
    return _poll_task is not None and not _poll_task.done()


async def resume_active_pollings() -> None:
    if (await divera_settings.get_config())["api_key"] and await _enabled_incidents():
        await _ensure_task()
