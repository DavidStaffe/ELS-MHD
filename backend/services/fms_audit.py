"""FMS-Audit-Trail: Aufzeichnung jeder FMS-Status-Aenderung pro Ressource.

Schreiben:
  - bei automatischem Divera-Sync (services/divera.py)
  - bei manueller PATCH-Aenderung von Resource.fms_status (routes/resources.py)

Lesen:
  - GET /api/incidents/{id}/fms-events
"""
import logging
import uuid
from typing import Any, Dict, Optional

from core.db import db
from core.time import iso, now_utc

logger = logging.getLogger(__name__)


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
    }
    try:
        await db.fms_events.insert_one(doc)
    except Exception as exc:  # pragma: no cover
        logger.exception("FMS-Event konnte nicht gespeichert werden: %s", exc)
        return None
    return {k: v for k, v in doc.items() if k != "_id"}
