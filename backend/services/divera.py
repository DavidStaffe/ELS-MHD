"""DIVERA transport and application of a shared vehicle snapshot.

Scheduling and encrypted settings live in divera_polling/divera_settings.
"""
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from core.db import db
from core.time import iso, now_utc
from services.realtime import publish_incident_event
from services.fms_audit import record_fms_change
from services.divera_settings import current_key

logger = logging.getLogger(__name__)
# httpx INFO includes URLs and therefore the DIVERA accesskey query parameter.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

DIVERA_BASE_URL = os.environ.get("DIVERA_BASE_URL", "https://www.divera247.com")

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

async def fetch_vehicles(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch all vehicles + FMS status from Divera. Returns list of dicts.

    Raises httpx.HTTPError on network errors, ValueError on API errors.
    """
    key = api_key if api_key is not None else await current_key()
    if not key:
        raise ValueError("DIVERA_API_KEY ist nicht konfiguriert")
    url = f"{DIVERA_BASE_URL}/api/v2/pull/vehicle-status"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params={"accesskey": key})
        resp.raise_for_status()
        data = resp.json()
    if not data.get("success"):
        raise ValueError("DIVERA hat die Anfrage abgelehnt.")
    vehicles = data.get("data")
    if not isinstance(vehicles, list) or any(not isinstance(v, dict) or "id" not in v for v in vehicles):
        raise ValueError("Ungültige DIVERA-Antwort.")
    return vehicles


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
    key = api_key if api_key is not None else await current_key()
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
        raise ValueError("DIVERA hat die Statusänderung abgelehnt.")
    return data if isinstance(data, dict) else {"raw": data}


async def apply_vehicles(incident_id: str, vehicles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Distribute one installation snapshot without making another API call."""
    result = {"ok": False, "matched": 0, "vehicles_total": len(vehicles), "timestamp": iso(now_utc())}
    by_id: Dict[str, Dict[str, Any]] = {str(v["id"]): v for v in vehicles}

    linked = await db.resources.find(
        {"incident_id": incident_id, "divera_id": {"$nin": [None, ""]}},
        {"_id": 0},
    ).to_list(None)

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


async def sync_incident(incident_id: str):
    """Compatibility entry point; all callers use the central coordinator."""
    from services.divera_polling import sync_incident as central_sync
    return await central_sync(incident_id)
