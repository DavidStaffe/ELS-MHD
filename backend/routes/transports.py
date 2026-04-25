"""Transports routes."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from core.db import db
from core.time import iso, now_utc
from models import Transport, TransportCreate, TransportUpdate
from services.seeds import (
    DEFAULT_ZIEL_BY_TYP,
    update_resource_status_by_name,
    release_bett_for_patient,
)
from services.funk import log_system_entry

router = APIRouter(prefix="/api", tags=["transports"])


@router.get("/incidents/{incident_id}/transports", response_model=List[dict])
async def list_transports(
    incident_id: str, typ: Optional[str] = None, status: Optional[str] = None
):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    query: dict = {"incident_id": incident_id}
    if typ:
        query["typ"] = {"$in": [v.strip() for v in typ.split(",") if v.strip()]}
    if status:
        query["status"] = {"$in": [v.strip() for v in status.split(",") if v.strip()]}
    return (
        await db.transports.find(query, {"_id": 0}).sort("created_at", 1).to_list(2000)
    )


@router.post(
    "/incidents/{incident_id}/transports", response_model=dict, status_code=201
)
async def create_transport(incident_id: str, payload: TransportCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    if inc.get("status") == "geplant":
        raise HTTPException(
            status_code=409,
            detail="Incident ist geplant. Transporte koennen erst im operativen Status angelegt werden",
        )
    p_kennung = None
    p_sichtung = None
    if payload.patient_id:
        p = await db.patients.find_one({"id": payload.patient_id}, {"_id": 0})
        if not p:
            raise HTTPException(status_code=404, detail="Patient nicht gefunden")
        if p.get("incident_id") != incident_id:
            raise HTTPException(
                status_code=400, detail="Patient gehoert nicht zu diesem Incident"
            )
        p_kennung = p.get("kennung")
        p_sichtung = p.get("sichtung")

    transport = Transport(
        incident_id=incident_id,
        patient_id=payload.patient_id,
        patient_kennung=p_kennung,
        patient_sichtung=p_sichtung,
        typ=payload.typ,
        ziel=payload.ziel or DEFAULT_ZIEL_BY_TYP.get(payload.typ, "sonstiges"),
        ressource=payload.ressource,
        notiz=payload.notiz,
        status="zugewiesen" if payload.ressource else "offen",
    )
    if payload.ressource:
        transport.zugewiesen_at = now_utc()
    doc = transport.model_dump()
    for k in (
        "created_at",
        "updated_at",
        "zugewiesen_at",
        "gestartet_at",
        "abgeschlossen_at",
    ):
        if isinstance(doc.get(k), datetime):
            doc[k] = iso(doc[k])
    await db.transports.insert_one(doc)
    if payload.ressource:
        await update_resource_status_by_name(
            incident_id, payload.ressource, "im_einsatz"
        )
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/transports/{transport_id}", response_model=dict)
async def get_transport(transport_id: str):
    d = await db.transports.find_one({"id": transport_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Transport nicht gefunden")
    return d


@router.patch("/transports/{transport_id}", response_model=dict)
async def update_transport(transport_id: str, payload: TransportUpdate):
    existing = await db.transports.find_one({"id": transport_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Transport nicht gefunden")
    inc = await db.incidents.find_one(
        {"id": existing["incident_id"]}, {"_id": 0, "status": 1}
    )
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Keine Aenderungen angegeben")
    if inc.get("status") == "geplant":
        raise HTTPException(
            status_code=409,
            detail="Incident ist geplant. Transportzuweisungen sind erst im operativen Status erlaubt",
        )
    now = now_utc()
    update["updated_at"] = iso(now)

    if "ressource" in update and update["ressource"]:
        if existing.get("status") in (None, "offen"):
            update.setdefault("status", "zugewiesen")
        if not existing.get("zugewiesen_at"):
            update["zugewiesen_at"] = iso(now)
    elif "ressource" in update and update["ressource"] in (None, ""):
        if existing.get("status") == "zugewiesen":
            update.setdefault("status", "offen")

    new_status = update.get("status")
    if new_status == "unterwegs" and not existing.get("gestartet_at"):
        update["gestartet_at"] = iso(now)
    if new_status == "abgeschlossen" and not existing.get("abgeschlossen_at"):
        update["abgeschlossen_at"] = iso(now)
    if new_status == "zugewiesen" and not existing.get("zugewiesen_at"):
        update["zugewiesen_at"] = iso(now)

    result = await db.transports.find_one_and_update(
        {"id": transport_id},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )

    existing_ressource = existing.get("ressource")
    new_ressource = result.get("ressource")
    new_status = result.get("status")

    async def _release_if_free(ressource_name: str):
        if not ressource_name:
            return
        other = await db.transports.find_one(
            {
                "incident_id": result["incident_id"],
                "ressource": ressource_name,
                "id": {"$ne": transport_id},
                "status": {"$in": ["zugewiesen", "unterwegs"]},
            },
            {"_id": 0},
        )
        if not other:
            await update_resource_status_by_name(
                result["incident_id"], ressource_name, "verfuegbar"
            )

    if existing_ressource and existing_ressource != new_ressource:
        await _release_if_free(existing_ressource)
    if new_ressource and new_status in ("zugewiesen", "unterwegs"):
        await update_resource_status_by_name(
            result["incident_id"], new_ressource, "im_einsatz"
        )
    if new_status == "abgeschlossen" and new_ressource:
        await _release_if_free(new_ressource)

    if new_status == "abgeschlossen" and result.get("patient_id"):
        await release_bett_for_patient(result["patient_id"])

    # Funktagebuch-Systemeintrag bei Status-Aenderung
    if "status" in update and update["status"] != existing.get("status"):
        kennung = result.get("patient_kennung") or "?"
        ress = result.get("ressource") or "-"
        await log_system_entry(
            incident_id=result["incident_id"],
            text=f"Transport {kennung} -> {update['status']} ({ress})",
            funk_typ="system",
            transport_id=transport_id,
            patient_id=result.get("patient_id"),
        )

    return result


@router.delete("/transports/{transport_id}", status_code=204)
async def delete_transport(transport_id: str):
    r = await db.transports.delete_one({"id": transport_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transport nicht gefunden")
    return None
