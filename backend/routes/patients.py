"""Patients routes."""

import asyncio
from datetime import datetime
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from core.auth import verify_access_token
from core.db import db
from core.permissions import IncidentAuth
from core.time import iso, now_utc
from models import Patient, PatientCreate, PatientUpdate
from routes.auth import require_admin
from services.seeds import (
    next_kennung,
    ensure_transport_for_patient,
    release_bett_for_patient,
)
from services.funk import log_system_entry
from services.realtime import (
    publish_patient_event,
    subscribe_patients,
    unsubscribe_patients,
)

router = APIRouter(prefix="/api", tags=["patients"])


# ---------------------------------------------------------------------------
# GET /incidents/{incident_id}/patients
# ---------------------------------------------------------------------------
@router.get("/incidents/{incident_id}/patients", response_model=List[dict])
async def list_patients(
    incident_id: str,
    sichtung: Optional[str] = None,
    status: Optional[str] = None,
    verbleib: Optional[str] = None,
    auth: IncidentAuth = Depends(IncidentAuth().require("read")),
):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    query: dict = {"incident_id": incident_id}
    if sichtung:
        vals = [v.strip() for v in sichtung.split(",") if v.strip()]
        if vals:
            query["sichtung"] = {"$in": vals}
    if status:
        vals = [v.strip() for v in status.split(",") if v.strip()]
        if vals:
            query["status"] = {"$in": vals}
    if verbleib:
        vals = [v.strip() for v in verbleib.split(",") if v.strip()]
        if vals:
            query["verbleib"] = {"$in": vals}

    return await db.patients.find(query, {"_id": 0}).sort("created_at", 1).to_list(2000)


# ---------------------------------------------------------------------------
# GET /incidents/{incident_id}/patients/stream  (SSE – Token via Query-Param)
# ---------------------------------------------------------------------------
@router.get("/incidents/{incident_id}/patients/stream")
async def stream_patients(
    incident_id: str,
    request: Request,
    token: str = Query(..., description="Gültiger Access-Token"),
):
    # Token-Validierung (SSE kann keine Auth-Header senden)
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Ungültiger oder abgelaufener Token")

    # Incident-Zugriff prüfen
    user_id = payload.get("sub")
    role = payload.get("role", "")
    if role != "admin":
        membership = await db.incident_roles.find_one(
            {"incident_id": incident_id, "user_id": user_id}
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Incident")

    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0, "id": 1})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    q = subscribe_patients(incident_id)

    async def event_gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=20.0)
                    payload_str = json.dumps(evt)
                    yield f"event: patient\ndata: {payload_str}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            unsubscribe_patients(incident_id, q)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# POST /incidents/{incident_id}/patients
# ---------------------------------------------------------------------------
@router.post("/incidents/{incident_id}/patients", response_model=dict, status_code=201)
async def create_patient(
    incident_id: str,
    payload: PatientCreate,
    auth: IncidentAuth = Depends(IncidentAuth().require("write")),
):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    if inc.get("status") == "geplant":
        raise HTTPException(
            status_code=409,
            detail="Incident ist geplant. Patienten koennen erst im operativen Status angelegt werden",
        )

    kennung = await next_kennung(incident_id)
    now = now_utc()
    patient = Patient(
        **payload.model_dump(exclude_none=True),
        incident_id=incident_id,
        kennung=kennung,
    )

    resource_change_ts = iso(now)
    if patient.behandlung_ressource_id:
        resource = await db.resources.find_one(
            {"id": patient.behandlung_ressource_id, "incident_id": incident_id},
            {"_id": 0, "id": 1, "name": 1},
        )
        if not resource:
            raise HTTPException(status_code=422, detail="Behandlungsressource nicht gefunden")
        patient.behandlung_ressource_name = resource.get("name")
        patient.behandlung_start_at = now
        patient.behandlung_ressource_events = [
            {
                "ts": resource_change_ts,
                "from_id": None,
                "from_name": None,
                "to_id": resource.get("id"),
                "to_name": resource.get("name"),
                "action": "assigned",
            }
        ]

    if patient.sichtung:
        patient.sichtung_at = now

    if payload.status == "wartend":
        patient.status = "in_behandlung"

    doc = patient.model_dump()
    for k in (
        "created_at",
        "updated_at",
        "sichtung_at",
        "behandlung_start_at",
        "transport_angefordert_at",
        "fallabschluss_at",
    ):
        if isinstance(doc.get(k), datetime):
            doc[k] = iso(doc[k])

    await db.patients.insert_one(doc)

    if patient.transport_typ:
        await ensure_transport_for_patient(doc)

    await log_system_entry(
        incident_id=incident_id,
        text=f"Patient {kennung} angelegt"
        + (f" (Sichtung {patient.sichtung})" if patient.sichtung else ""),
        funk_typ="system",
        prioritaet="kritisch" if patient.sichtung == "S1" else "normal",
        patient_id=patient.id,
    )
    await publish_patient_event(
        incident_id,
        {
            "kind": "patient",
            "action": "created",
            "patient_id": patient.id,
            "ts": iso(now_utc()),
        },
    )
    return {k: v for k, v in doc.items() if k != "_id"}


# ---------------------------------------------------------------------------
# GET /patients/{patient_id}
# ---------------------------------------------------------------------------
@router.get("/patients/{patient_id}", response_model=dict)
async def get_patient(
    patient_id: str,
    auth: IncidentAuth = Depends(IncidentAuth(id_source="patient").require("read")),
):
    d = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    return d


# ---------------------------------------------------------------------------
# PATCH /patients/{patient_id}
# ---------------------------------------------------------------------------
@router.patch("/patients/{patient_id}", response_model=dict)
async def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    auth: IncidentAuth = Depends(IncidentAuth(id_source="patient").require("write")),
):
    existing = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")

    # AL-Abschnitt-Check: Abschnittsleiter darf nur Patienten seines Abschnitts bearbeiten
    if auth.role == "al" and auth.abschnitt_id:
        if existing.get("abschnitt_id") != auth.abschnitt_id:
            raise HTTPException(
                status_code=403,
                detail="Abschnittsleiter darf nur Patienten des eigenen Abschnitts bearbeiten",
            )

    incident = await db.incidents.find_one(
        {"id": existing["incident_id"]}, {"_id": 0, "status": 1}
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Keine Aenderungen angegeben")

    if incident.get("status") == "geplant" and update.get("transport_typ"):
        raise HTTPException(
            status_code=409,
            detail="Incident ist geplant. Transportanforderungen sind erst im operativen Status erlaubt",
        )

    now = now_utc()
    update["updated_at"] = iso(now)

    if "sichtung" in update and not existing.get("sichtung_at"):
        update["sichtung_at"] = iso(now)

    if "sichtung" in update and existing.get("sichtung") != update["sichtung"]:
        sichtung_history = list(existing.get("sichtung_events") or [])
        sichtung_history.append(
            {
                "ts": iso(now),
                "from_sichtung": existing.get("sichtung"),
                "to_sichtung": update["sichtung"],
            }
        )
        update["sichtung_events"] = sichtung_history

    if "behandlung_ressource_id" in update:
        old_resource_id = existing.get("behandlung_ressource_id")
        old_resource_name = existing.get("behandlung_ressource_name")
        resource_id = update.get("behandlung_ressource_id")

        if resource_id in (None, ""):
            update["behandlung_ressource_id"] = None
            update["behandlung_ressource_name"] = None
            new_resource_id = None
            new_resource_name = None
        else:
            resource = await db.resources.find_one(
                {"id": resource_id, "incident_id": existing["incident_id"]},
                {"_id": 0, "id": 1, "name": 1},
            )
            if not resource:
                raise HTTPException(status_code=422, detail="Behandlungsressource nicht gefunden")
            update["behandlung_ressource_name"] = resource.get("name")
            new_resource_id = resource.get("id")
            new_resource_name = resource.get("name")
            if not existing.get("behandlung_start_at"):
                update["behandlung_start_at"] = iso(now)

        if old_resource_id != new_resource_id:
            history = list(existing.get("behandlung_ressource_events") or [])
            action = "assigned"
            if old_resource_id and new_resource_id:
                action = "changed"
            elif old_resource_id and not new_resource_id:
                action = "cleared"
            history.append(
                {
                    "ts": iso(now),
                    "from_id": old_resource_id,
                    "from_name": old_resource_name,
                    "to_id": new_resource_id,
                    "to_name": new_resource_name,
                    "action": action,
                }
            )
            update["behandlung_ressource_events"] = history

    if "transport_typ" in update and update["transport_typ"]:
        if existing.get("status") not in ("transportbereit", "uebergeben", "entlassen"):
            update.setdefault("status", "transportbereit")
        if not existing.get("transport_angefordert_at"):
            update["transport_angefordert_at"] = iso(now)

    if "fallabschluss_typ" in update and update["fallabschluss_typ"]:
        typ = update["fallabschluss_typ"]
        if typ == "rd_uebergabe":
            update.setdefault("status", "uebergeben")
            if not existing.get("verbleib") or existing.get("verbleib") == "unbekannt":
                update.setdefault("verbleib", "rd")
        elif typ == "entlassung":
            update.setdefault("status", "entlassen")
            if not existing.get("verbleib") or existing.get("verbleib") == "unbekannt":
                update.setdefault("verbleib", "event")
        elif typ == "manuell":
            update.setdefault("status", "entlassen")
        if not existing.get("fallabschluss_at"):
            update["fallabschluss_at"] = iso(now)

    new_status = update.get("status")
    if new_status == "transportbereit" and not existing.get("transport_angefordert_at"):
        update["transport_angefordert_at"] = iso(now)
    if new_status in ("entlassen", "uebergeben") and not existing.get("fallabschluss_at"):
        update["fallabschluss_at"] = iso(now)

    result = await db.patients.find_one_and_update(
        {"id": patient_id},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )

    if "transport_typ" in update and update["transport_typ"]:
        await ensure_transport_for_patient(result)

    if update.get("status") in ("uebergeben", "entlassen"):
        await db.transports.update_many(
            {"patient_id": patient_id, "status": {"$ne": "abgeschlossen"}},
            {
                "$set": {
                    "status": "abgeschlossen",
                    "abgeschlossen_at": iso(now),
                    "updated_at": iso(now),
                }
            },
        )
        await release_bett_for_patient(patient_id)
        await log_system_entry(
            incident_id=result["incident_id"],
            text=f"Fallabschluss {result.get('kennung')}: {update['status']}",
            funk_typ="system",
            patient_id=patient_id,
        )

    await publish_patient_event(
        result["incident_id"],
        {
            "kind": "patient",
            "action": "updated",
            "patient_id": patient_id,
            "ts": iso(now_utc()),
        },
    )
    return result


# ---------------------------------------------------------------------------
# POST /patients/{patient_id}/reopen  – EL / Admin only (assign_roles)
# ---------------------------------------------------------------------------
@router.post("/patients/{patient_id}/reopen", response_model=dict)
async def reopen_patient(
    patient_id: str,
    auth: IncidentAuth = Depends(IncidentAuth(id_source="patient").require("assign_roles")),
):
    """Wiedereröffnung eines abgeschlossenen Patienten.
    Nur EL oder Admin darf diese kritische klinische Entscheidung treffen.
    """
    existing = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")

    if existing.get("status") not in ("uebergeben", "entlassen"):
        raise HTTPException(
            status_code=409,
            detail="Patient ist nicht abgeschlossen und kann nicht wiedereroeffnet werden",
        )

    now = now_utc()
    ts = iso(now)
    history = list(existing.get("wiedereroeffnet_at") or [])
    history.append(ts)

    update = {
        "status": "in_behandlung",
        "fallabschluss_typ": None,
        "fallabschluss_at": None,
        "verbleib": "unbekannt",
        "wiedereroeffnet_at": history,
        "updated_at": ts,
    }

    result = await db.patients.find_one_and_update(
        {"id": patient_id},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )

    await log_system_entry(
        incident_id=result["incident_id"],
        text=f"Patient {result.get('kennung')} wiedereroeffnet",
        funk_typ="system",
        patient_id=patient_id,
    )
    await publish_patient_event(
        result["incident_id"],
        {
            "kind": "patient",
            "action": "reopened",
            "patient_id": patient_id,
            "ts": iso(now_utc()),
        },
    )
    return result


# ---------------------------------------------------------------------------
# DELETE /patients/{patient_id}  – Admin only
# ---------------------------------------------------------------------------
@router.delete("/patients/{patient_id}", status_code=204)
async def delete_patient(
    patient_id: str,
    _: dict = Depends(require_admin),
):
    existing = await db.patients.find_one(
        {"id": patient_id}, {"_id": 0, "incident_id": 1}
    )

    # Incident darf nicht bereits abgeschlossen sein
    if existing and existing.get("incident_id"):
        inc = await db.incidents.find_one(
            {"id": existing["incident_id"]}, {"_id": 0, "status": 1}
        )
        if inc and inc.get("status") == "abgeschlossen":
            raise HTTPException(
                status_code=409,
                detail="Patienten eines abgeschlossenen Incidents können nicht gelöscht werden",
            )

    result = await db.patients.delete_one({"id": patient_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")

    await db.transports.delete_many({"patient_id": patient_id})

    if existing and existing.get("incident_id"):
        await publish_patient_event(
            existing["incident_id"],
            {
                "kind": "patient",
                "action": "deleted",
                "patient_id": patient_id,
                "ts": iso(now_utc()),
            },
        )
    return None
