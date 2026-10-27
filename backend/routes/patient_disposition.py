"""Incident-local patient dispatch. DIVERA FMS and internal assignment are independent."""
from math import radians, sin, cos, asin, sqrt
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo import ReturnDocument

from core.db import db
from core.time import iso, now_utc
from services.realtime import publish_patient_event

router = APIRouter(prefix="/api", tags=["patient-disposition"])


class AssignRequest(BaseModel):
    resource_id: str


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [*a, *b])
    return 2 * 6371 * asin(sqrt(sin((lat2-lat1)/2)**2 +
                                cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2))


@router.get("/patients/{patient_id}/resource-suggestions")
async def resource_suggestions(patient_id: str):
    patient = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not patient:
        raise HTTPException(404, "Patient nicht gefunden")
    resources = await db.resources.find({"incident_id": patient["incident_id"]}, {"_id": 0}).to_list(500)
    sections = await db.abschnitte.find({"incident_id": patient["incident_id"], "aktiv": True},
                                        {"_id": 0}).to_list(200)
    section_by_id = {a["id"]: a for a in sections}
    patient_section = patient.get("abschnitt_id")
    pos = (patient.get("auffinde_lat"), patient.get("auffinde_lng"))
    has_pos = all(v is not None for v in pos)
    out = []
    for res in resources:
        if res.get("bound_patient_id") or res.get("status") != "verfuegbar":
            continue
        same_section = bool(patient_section and patient_section == res.get("abschnitt_id"))
        gps = (res.get("lat"), res.get("lng"))
        distance = km(pos, gps) if has_pos and all(v is not None for v in gps) else None
        # GPS estimates can be stale. Never silently describe them as current.
        tier = 0 if same_section else 1 if distance is not None else 2
        out.append({"resource_id": res["id"], "name": res.get("name"),
                    "abschnitt_id": res.get("abschnitt_id"),
                    "abschnitt_name": section_by_id.get(res.get("abschnitt_id"), {}).get("name"),
                    "reason": "eigener_abschnitt" if same_section else
                              "positionsnaehe_ungeprueft" if distance is not None else "sonstige_freie",
                    "distance_km_airline": round(distance, 2) if distance is not None else None,
                    "priority": tier})
    out.sort(key=lambda r: (r["priority"], r["distance_km_airline"] if r["distance_km_airline"] is not None else float("inf"), r["name"] or ""))
    return out


@router.post("/patients/{patient_id}/assign-resource")
async def assign_resource(patient_id: str, payload: AssignRequest):
    patient = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not patient:
        raise HTTPException(404, "Patient nicht gefunden")
    if patient.get("status") in ("entlassen", "uebergeben"):
        raise HTTPException(409, "Abgeschlossener Patient kann nicht disponiert werden")
    if patient.get("zugewiesene_ressource_id"):
        raise HTTPException(409, "Patient hat bereits eine disponierte Ressource")
    timestamp = iso(now_utc())
    # Compare-and-set guarantees one active patient even under competing requests.
    resource = await db.resources.find_one_and_update(
        {"id": payload.resource_id, "incident_id": patient["incident_id"],
         "status": "verfuegbar", "bound_patient_id": None},
        {"$set": {"bound_patient_id": patient_id, "updated_at": timestamp}},
        return_document=ReturnDocument.AFTER, projection={"_id": 0})
    if not resource:
        # Backward-compatible documents without the new binding field.
        resource = await db.resources.find_one_and_update(
            {"id": payload.resource_id, "incident_id": patient["incident_id"],
             "status": "verfuegbar", "bound_patient_id": {"$exists": False}},
            {"$set": {"bound_patient_id": patient_id, "updated_at": timestamp}},
            return_document=ReturnDocument.AFTER, projection={"_id": 0})
    if not resource:
        raise HTTPException(409, "Ressource nicht verfügbar oder bereits einem Patienten zugewiesen")
    updated = await db.patients.find_one_and_update(
        {"id": patient_id, "zugewiesene_ressource_id": None},
        {"$set": {"zugewiesene_ressource_id": payload.resource_id, "updated_at": timestamp},
         "$push": {"disposition_events": {"ts": timestamp, "type": "assigned",
                                           "resource_id": payload.resource_id,
                                           "entered_by": None}}},
        return_document=ReturnDocument.AFTER, projection={"_id": 0})
    if not updated:
        await db.resources.update_one({"id": payload.resource_id, "bound_patient_id": patient_id},
                                      {"$set": {"bound_patient_id": None}})
        raise HTTPException(409, "Patient wurde zwischenzeitlich anderweitig zugewiesen")
    await publish_patient_event(patient["incident_id"], {"kind": "patient", "action": "dispatched",
                                                           "patient_id": patient_id, "ts": timestamp})
    return updated


@router.post("/resources/{resource_id}/release-from-patient")
async def release_resource(resource_id: str):
    # Authentication/EL-only server authorization must be added with the agreed future login.
    resource = await db.resources.find_one({"id": resource_id}, {"_id": 0})
    if not resource:
        raise HTTPException(404, "Ressource nicht gefunden")
    pid = resource.get("bound_patient_id")
    if not pid:
        raise HTTPException(409, "Ressource hat keine aktive Patientenbindung")
    timestamp = iso(now_utc())
    changed = await db.resources.find_one_and_update(
        {"id": resource_id, "bound_patient_id": pid},
        {"$set": {"bound_patient_id": None, "updated_at": timestamp}},
        return_document=ReturnDocument.AFTER)
    if not changed:
        raise HTTPException(409, "Ressourcenbindung wurde zwischenzeitlich geändert")
    await db.patients.update_one(
        {"id": pid, "zugewiesene_ressource_id": resource_id},
        {"$set": {"zugewiesene_ressource_id": None, "updated_at": timestamp},
         "$push": {"disposition_events": {"ts": timestamp, "type": "released",
                                           "resource_id": resource_id, "entered_by": None}}})
    await publish_patient_event(resource["incident_id"], {"kind": "patient", "action": "resource_released",
                                                            "patient_id": pid, "ts": timestamp})
    return {"released": True, "patient_id": pid}
