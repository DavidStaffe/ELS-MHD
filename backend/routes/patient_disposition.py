"""Incident-local patient dispatch. DIVERA FMS and internal assignment are independent."""
from math import radians, sin, cos, asin, sqrt
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
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


def section_neighbors(a: dict | None, b: dict | None) -> bool:
    """Approximate adjacency from documented section polygons (not guessed names)."""
    if not a or not b or not a.get("polygon") or not b.get("polygon"):
        return False
    pa, pb = a["polygon"], b["polygon"]
    if len(pa) < 3 or len(pb) < 3:
        return False
    # Project to approximate local meters, then calculate vertex-to-segment
    # boundary separation. Adjacent polygons need not share exact vertices.
    mid_lat = radians(sum(v[0] for v in pa + pb) / (len(pa) + len(pb)))
    def xy(point):
        return (point[1] * 111320 * cos(mid_lat), point[0] * 111320)
    def point_segment_distance(p, q, r):
        dx, dy = r[0]-q[0], r[1]-q[1]
        denom = dx*dx+dy*dy
        t = max(0, min(1, ((p[0]-q[0])*dx+(p[1]-q[1])*dy)/denom)) if denom else 0
        return sqrt((p[0]-(q[0]+t*dx))**2+(p[1]-(q[1]+t*dy))**2)
    aa, bb = list(map(xy, pa)), list(map(xy, pb))
    for coords, others in ((aa, bb), (bb, aa)):
        for point in coords:
            for i, first in enumerate(others):
                second = others[(i+1) % len(others)]
                if point_segment_distance(point, first, second) <= 25:
                    return True
    return False


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
    own_section = section_by_id.get(patient_section)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for res in resources:
        if res.get("bound_patient_id") or res.get("status") != "verfuegbar":
            continue
        same_section = bool(patient_section and patient_section == res.get("abschnitt_id"))
        gps = (res.get("lat"), res.get("lng"))
        age = None
        if res.get("position_updated_at"):
            try:
                stamp = datetime.fromisoformat(res["position_updated_at"].replace("Z", "+00:00"))
                age = (now - stamp).total_seconds()
            except (TypeError, ValueError):
                pass
        fresh_gps = age is not None and 0 <= age <= 300
        distance = km(pos, gps) if has_pos and fresh_gps and all(v is not None for v in gps) else None
        neighbor = section_neighbors(own_section, section_by_id.get(res.get("abschnitt_id")))
        tier = 0 if same_section else 1 if distance is not None else 2 if neighbor else 3
        out.append({"resource_id": res["id"], "name": res.get("name"),
                    "abschnitt_id": res.get("abschnitt_id"),
                    "abschnitt_name": section_by_id.get(res.get("abschnitt_id"), {}).get("name"),
                    "reason": "eigener_abschnitt" if same_section else
                              "positionsnaehe" if distance is not None else
                              "nachbarabschnitt" if neighbor else "sonstige_freie",
                    "distance_km_airline": round(distance, 2) if distance is not None else None,
                    "priority": tier})
    out.sort(key=lambda r: (r["priority"], r["distance_km_airline"] if r["distance_km_airline"] is not None else float("inf"), r["name"] or ""))
    return out


@router.post("/patients/{patient_id}/assign-resource")
async def assign_resource(patient_id: str, payload: AssignRequest, request: Request):
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
                                           "entered_by": request.state.user["id"]}}},
        return_document=ReturnDocument.AFTER, projection={"_id": 0})
    if not updated:
        await db.resources.update_one({"id": payload.resource_id, "bound_patient_id": patient_id},
                                      {"$set": {"bound_patient_id": None}})
        raise HTTPException(409, "Patient wurde zwischenzeitlich anderweitig zugewiesen")
    await publish_patient_event(patient["incident_id"], {"kind": "patient", "action": "dispatched",
                                                           "patient_id": patient_id, "ts": timestamp})
    return updated


@router.post("/resources/{resource_id}/release-from-patient")
async def release_resource(resource_id: str, request: Request):
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
                                           "resource_id": resource_id, "entered_by": request.state.user["id"]}}})
    await publish_patient_event(resource["incident_id"], {"kind": "patient", "action": "resource_released",
                                                            "patient_id": pid, "ts": timestamp})
    return {"released": True, "patient_id": pid}
