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
from services.realtime import publish_incident_event

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
    payload = {k: v for k, v in doc.items() if k != "_id"}
    # SSE-Push: Echtzeit-Benachrichtigung an alle verbundenen Clients (besonders
    # wichtig fuer FMS-5/0-Sprechwunsch-Alarme, damit die Glocke sofort reagiert).
    try:
        await publish_incident_event({
            "kind": "fms_event",
            "action": "created",
            "incident_id": incident_id,
            "is_alert": payload.get("is_alert", False),
            "event": payload,
        })
    except Exception:  # pragma: no cover
        pass
    return payload


async def acknowledge_fms_event(
    event_id: str,
    role: str,
    name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Quittiert ein FMS-5/0-Event:
      1. Setzt acknowledged_by_role + acknowledged_by_name + acknowledged_at am Event.
      2. Wenn die Resource an Divera verknuepft ist UND vorher ein regulaerer
         FMS-Status (1-4,6-9) gesetzt war: ruft Divera-FMS-API auf, um den
         vorherigen Status wiederherzustellen und die Nachricht "SPRECHEN SIE"
         per status_note an das Fahrzeug zu schicken.
      3. Aktualisiert lokal Resource.fms_status auf den vorherigen Wert
         (damit Karte+UI sofort konsistent sind, auch falls Divera-Polling
         noch nicht gelaufen ist).

    Returns updated event dict, or None if event was not found.
    Raises ValueError when event is not an alert (FMS 5/0) or already acknowledged.
    """
    # Lokaler Import um zirkulaere Imports zu vermeiden (divera importiert fms_audit).
    from services import divera as divera_service

    existing = await db.fms_events.find_one({"id": event_id}, {"_id": 0})
    if not existing:
        return None
    if not existing.get("is_alert") and existing.get("to_fms") not in ALERT_FMS_CODES:
        raise ValueError("Nur FMS-5/0-Events koennen quittiert werden.")
    if existing.get("acknowledged_at"):
        raise ValueError("Event ist bereits quittiert.")

    set_fields: Dict[str, Any] = {
        "acknowledged_by_role": role,
        "acknowledged_by_name": (name or "").strip() or None,
        "acknowledged_at": iso(now_utc()),
    }

    # Status-Revert + "SPRECHEN SIE" an Divera
    from_fms = existing.get("from_fms")
    divera_id = existing.get("divera_id")
    resource_id = existing.get("resource_id")
    revert_target: Optional[int] = None
    if isinstance(from_fms, int) and from_fms not in ALERT_FMS_CODES:
        revert_target = from_fms

    divera_sent = False
    divera_error: Optional[str] = None
    if revert_target is not None and divera_id:
        try:
            await divera_service.set_vehicle_status(
                divera_id=str(divera_id),
                status_id=revert_target,
                status_note="SPRECHEN SIE",
            )
            divera_sent = True
        except Exception as exc:  # noqa: BLE001 — log + keep going
            divera_error = str(exc)[:200]
            logger.warning(
                "Divera-Revert fehlgeschlagen fuer event=%s vehicle=%s: %s",
                event_id, divera_id, exc,
            )

    # Lokale Resource zuruecksetzen (egal ob Divera-Call funktioniert hat —
    # die naechste Polling-Iteration korrigiert ggf. Differenzen).
    if revert_target is not None and resource_id:
        try:
            # FMS-Status-zu-Resource-Status-Mapping aus divera-service
            new_status = divera_service._FMS_TO_RESOURCE_STATUS.get(revert_target)
            resource_update: Dict[str, Any] = {
                "fms_status": revert_target,
                "updated_at": iso(now_utc()),
            }
            if new_status:
                resource_update["status"] = new_status
            await db.resources.update_one(
                {"id": resource_id},
                {"$set": resource_update},
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("Lokales Resource-Revert fehlgeschlagen: %s", exc)

    set_fields["reverted_to_fms"] = revert_target
    set_fields["revert_sent_to_divera"] = divera_sent
    if divera_error:
        set_fields["revert_divera_error"] = divera_error

    updated = await db.fms_events.find_one_and_update(
        {"id": event_id},
        {"$set": set_fields},
        return_document=True,
        projection={"_id": 0},
    )

    # SSE-Push: Resource-Refresh triggern damit Karte sofort aktualisiert
    if revert_target is not None and resource_id:
        try:
            await publish_incident_event({
                "kind": "resource",
                "action": "fms_reverted",
                "incident_id": existing.get("incident_id"),
                "resource_id": resource_id,
                "fms_status": revert_target,
                "ts": iso(now_utc()),
            })
        except Exception:  # pragma: no cover
            pass

    return updated
