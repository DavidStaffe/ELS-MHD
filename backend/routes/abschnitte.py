"""Abschnitte routes (Schritt 10)."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from core.db import db
from core.time import iso
from models import Abschnitt, AbschnittCreate, AbschnittUpdate

router = APIRouter(prefix="/api", tags=["abschnitte"])


@router.get("/incidents/{incident_id}/abschnitte", response_model=List[dict])
async def list_abschnitte(incident_id: str, aktiv: Optional[bool] = None):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    query: dict = {"incident_id": incident_id}
    if aktiv is not None:
        query["aktiv"] = aktiv
    return await db.abschnitte.find(query, {"_id": 0}).sort("erstellt_um", 1).to_list(200)


@router.post("/incidents/{incident_id}/abschnitte", response_model=dict, status_code=201)
async def create_abschnitt(incident_id: str, payload: AbschnittCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    a = Abschnitt(incident_id=incident_id, **payload.model_dump(exclude_unset=True))
    d = a.model_dump()
    if isinstance(d.get("erstellt_um"), datetime):
        d["erstellt_um"] = iso(d["erstellt_um"])
    await db.abschnitte.insert_one(d)
    return {k: v for k, v in d.items() if k != "_id"}


@router.get("/abschnitte/{abschnitt_id}", response_model=dict)
async def get_abschnitt(abschnitt_id: str):
    d = await db.abschnitte.find_one({"id": abschnitt_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Abschnitt nicht gefunden")
    return d


@router.patch("/abschnitte/{abschnitt_id}", response_model=dict)
async def update_abschnitt(abschnitt_id: str, payload: AbschnittUpdate):
    # exclude_unset to allow clearing polygon via explicit null
    upd = payload.model_dump(exclude_unset=True)
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    res = await db.abschnitte.find_one_and_update(
        {"id": abschnitt_id}, {"$set": upd},
        return_document=True, projection={"_id": 0},
    )
    if not res:
        raise HTTPException(status_code=404, detail="Abschnitt nicht gefunden")
    return res


@router.delete("/abschnitte/{abschnitt_id}", status_code=204)
async def delete_abschnitt(abschnitt_id: str):
    a = await db.abschnitte.find_one({"id": abschnitt_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Abschnitt nicht gefunden")
    # Loeschen NUR erlaubt wenn keine Betten des Abschnitts belegt sind.
    # (Betten in Status 'frei' oder 'gesperrt' werden mit-entkoppelt und bleiben
    # als orphan im System, koennen anderem Abschnitt zugeordnet werden.)
    occupied = await db.betten.count_documents({
        "abschnitt_id": abschnitt_id,
        "status": "belegt",
    })
    if occupied > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Abschnitt nicht loeschbar: {occupied} Bett(en) belegt. "
                "Patienten bitte zuerst freigeben oder verlegen."
            ),
        )
    await db.resources.update_many(
        {"abschnitt_id": abschnitt_id}, {"$set": {"abschnitt_id": None}},
    )
    await db.betten.update_many(
        {"abschnitt_id": abschnitt_id}, {"$set": {"abschnitt_id": None}},
    )
    await db.abschnitte.delete_one({"id": abschnitt_id})
    return None
