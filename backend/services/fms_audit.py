"""FMS-Audit-Trail: Aufzeichnung jeder FMS-Status-Aenderung pro Ressource.

Schreiben:
  - bei automatischem Divera-Sync (services/divera.py)
  - bei manueller PATCH-Aenderung von Resource.fms_status (routes/resources.py)

Lesen:
  - GET /api/incidents/{id}/fms-events

Quittieren (FMS 5/0 Alerts):
  - POST /api/fms-events/{event_id}/acknowledge
"""
import logging
import uuid
from typing import Any, Dict, Optional

from core.db import db
from core.time import iso, now_utc

logger = logging.getLogger(__name__)

# FMS-Codes die einen Sprechwunsch-Alarm ausloesen.
ALERT_FMS_CODES = {0, 5}


async def record_fms_change(
    *,
    incident_id: str,
    resource_id: str,
    resource_name: str,
    from_fms: Optional[int],
    to_fms: Optional[int],
    from_status: Optional[str],
    to_status: Optional[str],
    source: str = "manual",   # "divera" | "manual"
    vehicle_name: Optional[str] = None,
    divera_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Schreibe FMS-Event, wenn sich from_fms vs. to_fms unterscheidet.

    Returns the inserted event dict, or None if nothing changed.
    """
    if from_fms == to_fms:
        return None
    doc = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "vehicle_name": vehicle_name,
        "divera_id": divera_id,
        "from_fms": from_fms,
        "to_fms": to_fms,
        "from_status": from_status,
        "to_status": to_status,
        "source": source,
        "ts": iso(now_utc()),
        # Quittierungsfelder (nur fuer Alert-Codes 0/5 relevant, sonst None)
        "is_alert": to_fms in ALERT_FMS_CODES,
        "acknowledged_by_role": None,
        "acknowledged_at": None,
    }
    try:
        await db.fms_events.insert_one(doc)
    except Exception as exc:  # pragma: no cover
        logger.exception("FMS-Event konnte nicht gespeichert werden: %s", exc)
        return None
    return {k: v for k, v in doc.items() if k != "_id"}


async def acknowledge_fms_event(
    event_id: str,
    role: str,
) -> Optional[Dict[str, Any]]:
    """Setzt acknowledged_by_role + acknowledged_at fuer ein FMS-Event.

    Returns updated event dict, or None if event was not found.
    Raises ValueError when event is not an alert (FMS 5/0) or already acknowledged.
    """
    existing = await db.fms_events.find_one({"id": event_id}, {"_id": 0})
    if not existing:
        return None
    if not existing.get("is_alert") and existing.get("to_fms") not in ALERT_FMS_CODES:
        raise ValueError("Nur FMS-5/0-Events koennen quittiert werden.")
    if existing.get("acknowledged_at"):
        raise ValueError("Event ist bereits quittiert.")
    updated = await db.fms_events.find_one_and_update(
        {"id": event_id},
        {"$set": {
            "acknowledged_by_role": role,
            "acknowledged_at": iso(now_utc()),
        }},
        return_document=True,
        projection={"_id": 0},
    )
    return updated
