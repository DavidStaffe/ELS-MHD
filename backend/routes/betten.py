"""Behandlungsbetten routes (Schritt 11)."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from core.db import db
from core.time import iso, now_utc
from models import Bett, BettCreate, BettUpdate, BettBulkCreate, BettAssign

router = APIRouter(prefix="/api", tags=["betten"])


@router.get("/incidents/{incident_id}/betten", response_model=List[dict])
async def list_betten(incident_id: str, status: Optional[str] = None, abschnitt_id: Optional[str] = None):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    query: dict = {"incident_id": incident_id}
    if status:
        query["status"] = {"$in": [v.strip() for v in status.split(",") if v.strip()]}
    if abschnitt_id:
        query["abschnitt_id"] = abschnitt_id
    return await db.betten.find(query, {"_id": 0}).sort("erstellt_um", 1).to_list(500)


@router.post("/incidents/{incident_id}/betten", response_model=dict, status_code=201)
async def create_bett(incident_id: str, payload: BettCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    b = Bett(incident_id=incident_id, **payload.model_dump(exclude_none=True))
    d = b.model_dump()
    for k in ("belegt_seit", "erstellt_um"):
        if isinstance(d.get(k), datetime):
            d[k] = iso(d[k])
    await db.betten.insert_one(d)
    return {k: v for k, v in d.items() if k != "_id"}


@router.post("/incidents/{incident_id}/betten/bulk", response_model=List[dict], status_code=201)
async def create_betten_bulk(incident_id: str, payload: BettBulkCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    docs = []
    for i in range(payload.anzahl):
        b = Bett(
            incident_id=incident_id,
            name=f"{payload.praefix} {payload.start_index + i}",
            typ=payload.typ,
            abschnitt_id=payload.abschnitt_id,
        )
        d = b.model_dump()
        for k in ("belegt_seit", "erstellt_um"):
            if isinstance(d.get(k), datetime):
                d[k] = iso(d[k])
        docs.append(d)
    if docs:
        await db.betten.insert_many(docs)
    return [{k: v for k, v in d.items() if k != "_id"} for d in docs]


@router.get("/betten/{bett_id}", response_model=dict)
async def get_bett(bett_id: str):
    d = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    return d


@router.patch("/betten/{bett_id}", response_model=dict)
async def update_bett(bett_id: str, payload: BettUpdate):
    upd = payload.model_dump(exclude_none=True)
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    res = await db.betten.find_one_and_update(
        {"id": bett_id}, {"$set": upd},
        return_document=True, projection={"_id": 0},
    )
    if not res:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    return res


@router.delete("/betten/{bett_id}", status_code=204)
async def delete_bett(bett_id: str):
    b = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    if not b:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    if b.get("status") == "belegt" or b.get("patient_id"):
        raise HTTPException(
            status_code=409,
            detail="Belegtes Bett kann nicht geloescht werden. Erst Patient entfernen.",
        )
    await db.betten.delete_one({"id": bett_id})
    return None


@router.post("/betten/{bett_id}/assign", response_model=dict)
async def assign_bett(bett_id: str, payload: BettAssign):
    bett = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    if not bett:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    if bett.get("status") == "gesperrt":
        raise HTTPException(status_code=409, detail="Bett ist gesperrt")
    if bett.get("status") == "belegt" and bett.get("patient_id") != payload.patient_id:
        raise HTTPException(status_code=409, detail="Bett bereits belegt")

    patient = await db.patients.find_one({"id": payload.patient_id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    if patient.get("incident_id") != bett.get("incident_id"):
        raise HTTPException(status_code=400, detail="Patient gehoert nicht zu diesem Incident")

    now = now_utc()
    if patient.get("bett_id") and patient["bett_id"] != bett_id:
        await db.betten.update_one(
            {"id": patient["bett_id"]},
            {"$set": {"status": "frei", "patient_id": None, "belegt_seit": None}},
        )
    await db.betten.update_one(
        {"id": bett_id},
        {"$set": {"status": "belegt", "patient_id": payload.patient_id, "belegt_seit": iso(now)}},
    )
    await db.patients.update_one(
        {"id": payload.patient_id},
        {"$set": {"bett_id": bett_id, "updated_at": iso(now)}},
    )
    return await db.betten.find_one({"id": bett_id}, {"_id": 0})


@router.post("/betten/{bett_id}/release", response_model=dict)
async def release_bett(bett_id: str):
    bett = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    if not bett:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    pid = bett.get("patient_id")
    await db.betten.update_one(
        {"id": bett_id},
        {"$set": {"status": "frei", "patient_id": None, "belegt_seit": None}},
    )
    if pid:
        await db.patients.update_one(
            {"id": pid, "bett_id": bett_id},
            {"$set": {"bett_id": None, "updated_at": iso(now_utc())}},
        )
    return await db.betten.find_one({"id": bett_id}, {"_id": 0})
