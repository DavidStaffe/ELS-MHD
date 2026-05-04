"""Abschnitte routes – secured with RBAC."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.permissions import IncidentAuth
from core.time import iso
from models import Abschnitt, AbschnittCreate, AbschnittUpdate

router = APIRouter(prefix="/api", tags=["abschnitte"])


@router.get("/incidents/{incident_id}/abschnitte", response_model=List[dict])
async def list_abschnitte(
    incident_id: str,
    aktiv: Optional[bool] = None,
    auth=Depends(IncidentAuth().require("read")),
):
    query: dict = {"incident_id": incident_id}
    if aktiv is not None:
        query["aktiv"] = aktiv
    return (
        await db.abschnitte.find(query, {"_id": 0})
        .sort("erstellt_um", 1)
        .to_list(200)
    )


@router.post("/incidents/{incident_id}/abschnitte", response_model=dict, status_code=201)
async def create_abschnitt(
    incident_id: str,
    payload: AbschnittCreate,
    auth=Depends(IncidentAuth().require("write")),
):
    # Incident-Existenz-Prüfung übernimmt IncidentAuth bereits implizit;
    # wir prüfen trotzdem explizit für den 404-Case (kein Incident, kein Zugriff).
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    a = Abschnitt(incident_id=incident_id, **payload.model_dump(exclude_none=True))
    d = a.model_dump()
    if isinstance(d.get("erstellt_um"), datetime):
        d["erstellt_um"] = iso(d["erstellt_um"])
    await db.abschnitte.insert_one(d)
    return {k: v for k, v in d.items() if k != "_id"}


@router.get("/abschnitte/{abschnitt_id}", response_model=dict)
async def get_abschnitt(
    abschnitt_id: str,
    auth=Depends(IncidentAuth(id_source="abschnitt").require("read")),
):
    d = await db.abschnitte.find_one({"id": abschnitt_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Abschnitt nicht gefunden")
    return d


@router.patch("/abschnitte/{abschnitt_id}", response_model=dict)
async def update_abschnitt(
    abschnitt_id: str,
    payload: AbschnittUpdate,
    auth=Depends(IncidentAuth(id_source="abschnitt").require("write")),
):
    upd = payload.model_dump(exclude_none=True)
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    res = await db.abschnitte.find_one_and_update(
        {"id": abschnitt_id},
        {"$set": upd},
        return_document=True,
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(status_code=404, detail="Abschnitt nicht gefunden")
    return res


@router.delete("/abschnitte/{abschnitt_id}", status_code=204)
async def delete_abschnitt(
    abschnitt_id: str,
    auth=Depends(IncidentAuth(id_source="abschnitt").require("write")),
):
    a = await db.abschnitte.find_one({"id": abschnitt_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Abschnitt nicht gefunden")

    inc = await db.incidents.find_one({"id": a["incident_id"]}, {"_id": 0})
    if inc and inc.get("status") in ("operativ", "geplant"):
        raise HTTPException(
            status_code=409,
            detail="Abschnitt kann bei laufendem Incident nur deaktiviert, nicht geloescht werden",
        )

    await db.resources.update_many(
        {"abschnitt_id": abschnitt_id}, {"$set": {"abschnitt_id": None}}
    )
    await db.betten.update_many(
        {"abschnitt_id": abschnitt_id}, {"$set": {"abschnitt_id": None}}
    )
    await db.abschnitte.delete_one({"id": abschnitt_id})
    return None
