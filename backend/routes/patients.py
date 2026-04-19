"""Patients routes."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from core.db import db
from core.time import iso, now_utc
from models import Patient, PatientCreate, PatientUpdate
from services.seeds import next_kennung, ensure_transport_for_patient, release_bett_for_patient
from services.funk import log_system_entry

router = APIRouter(prefix="/api", tags=["patients"])


@router.get("/incidents/{incident_id}/patients", response_model=List[dict])
async def list_patients(
    incident_id: str,
    sichtung: Optional[str] = None,
    status: Optional[str] = None,
    verbleib: Optional[str] = None,
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


@router.post("/incidents/{incident_id}/patients", response_model=dict, status_code=201)
async def create_patient(incident_id: str, payload: PatientCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    kennung = await next_kennung(incident_id)
    now = now_utc()
    patient = Patient(
        **payload.model_dump(exclude_none=True),
        incident_id=incident_id, kennung=kennung,
    )
    if patient.sichtung:
        patient.sichtung_at = now
        patient.behandlung_start_at = now
        if payload.status == "wartend":
            patient.status = "in_behandlung"
    doc = patient.model_dump()
    for k in ("created_at", "updated_at", "sichtung_at", "behandlung_start_at",
              "transport_angefordert_at", "fallabschluss_at"):
        if isinstance(doc.get(k), datetime):
            doc[k] = iso(doc[k])
    await db.patients.insert_one(doc)
    await log_system_entry(
        incident_id=incident_id,
        text=f"Patient {kennung} angelegt" + (f" (Sichtung {patient.sichtung})" if patient.sichtung else ""),
        funk_typ="system",
        prioritaet="kritisch" if patient.sichtung == "S1" else "normal",
        patient_id=patient.id,
    )
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/patients/{patient_id}", response_model=dict)
async def get_patient(patient_id: str):
    d = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    return d


@router.patch("/patients/{patient_id}", response_model=dict)
async def update_patient(patient_id: str, payload: PatientUpdate):
    existing = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Keine Aenderungen angegeben")
    now = now_utc()
    update["updated_at"] = iso(now)

    if "sichtung" in update and not existing.get("sichtung_at"):
        update["sichtung_at"] = iso(now)
        if not existing.get("behandlung_start_at"):
            update["behandlung_start_at"] = iso(now)

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
        {"id": patient_id}, {"$set": update},
        return_document=True, projection={"_id": 0},
    )
    if "transport_typ" in update and update["transport_typ"]:
        await ensure_transport_for_patient(result)
    if update.get("status") in ("uebergeben", "entlassen"):
        await db.transports.update_many(
            {"patient_id": patient_id, "status": {"$ne": "abgeschlossen"}},
            {"$set": {"status": "abgeschlossen",
                      "abgeschlossen_at": iso(now), "updated_at": iso(now)}},
        )
        await release_bett_for_patient(patient_id)
        await log_system_entry(
            incident_id=result["incident_id"],
            text=f"Fallabschluss {result.get('kennung')}: {update['status']}",
            funk_typ="system",
            patient_id=patient_id,
        )
    return result


@router.post("/patients/{patient_id}/reopen", response_model=dict)
async def reopen_patient(patient_id: str):
    """Wiedereroeffnung eines abgeschlossenen Patienten.

    Nutzung: Patient wurde entlassen/uebergeben, kehrt aber zurueck und muss
    erneut versorgt werden. Setzt Status auf 'in_behandlung' zurueck, hebt
    Fallabschluss auf und haengt den Zeitstempel an `wiedereroeffnet_at`.
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
        {"id": patient_id}, {"$set": update},
        return_document=True, projection={"_id": 0},
    )
    await log_system_entry(
        incident_id=result["incident_id"],
        text=f"Patient {result.get('kennung')} wiedereroeffnet",
        funk_typ="system",
        patient_id=patient_id,
    )
    return result


@router.delete("/patients/{patient_id}", status_code=204)
async def delete_patient(patient_id: str):
    result = await db.patients.delete_one({"id": patient_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    await db.transports.delete_many({"patient_id": patient_id})
    return None
