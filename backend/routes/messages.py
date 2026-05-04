"""Messages / Funktagebuch routes – secured with RBAC."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.db import db
from core.permissions import IncidentAuth
from core.time import iso, now_utc
from models import MessageConfirm, MessageCreate, MessageUpdate

router = APIRouter(prefix="/api", tags=["messages"])


def _doc_defaults() -> dict:
    return {
        "quittiert_at": None,
        "quittiert_von": None,
        "bestaetigt_at": None,
        "bestaetigt_von": None,
        "finalisiert": False,
        "finalisiert_at": None,
        "finalisiert_von": None,
        "quelle": "manuell",
    }


@router.get("/incidents/{incident_id}/messages", response_model=List[dict])
async def list_messages(
    incident_id: str,
    open_only: bool = False,
    funk_typ: Optional[str] = Query(default=None),
    prioritaet: Optional[str] = None,
    quelle: Optional[str] = None,
    abschnitt_id: Optional[str] = None,
    absender: Optional[str] = None,
    empfaenger: Optional[str] = None,
    q: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    auth=Depends(IncidentAuth().require("read")),
):
    query: dict = {"incident_id": incident_id}
    if open_only:
        query["quittiert_at"] = None
    if funk_typ:
        query["funk_typ"] = {"$in": [v.strip() for v in funk_typ.split(",") if v.strip()]}
    if prioritaet:
        query["prioritaet"] = {"$in": [v.strip() for v in prioritaet.split(",") if v.strip()]}
    if quelle:
        query["quelle"] = {"$in": [v.strip() for v in quelle.split(",") if v.strip()]}
    if abschnitt_id:
        query["abschnitt_id"] = abschnitt_id
    if absender:
        query["absender"] = {"$regex": absender, "$options": "i"}
    if empfaenger:
        query["empfaenger"] = {"$regex": empfaenger, "$options": "i"}
    if q:
        query["$or"] = [
            {"text": {"$regex": q, "$options": "i"}},
            {"absender": {"$regex": q, "$options": "i"}},
            {"empfaenger": {"$regex": q, "$options": "i"}},
        ]
    if since:
        query.setdefault("created_at", {})["$gte"] = since
    if until:
        query.setdefault("created_at", {})["$lte"] = until
    return await db.messages.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)


@router.post("/incidents/{incident_id}/messages", response_model=dict, status_code=201)
async def create_message(
    incident_id: str,
    payload: MessageCreate,
    auth=Depends(IncidentAuth().require("write")),
):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    doc = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        **payload.model_dump(exclude_none=True),
        **_doc_defaults(),
        "created_at": iso(now_utc()),
    }
    doc.setdefault("funk_typ", "lage")
    doc.setdefault("absender", payload.von or "")
    doc.setdefault("empfaenger", "")
    await db.messages.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/messages/{message_id}", response_model=dict)
async def get_message(
    message_id: str,
    auth=Depends(IncidentAuth(id_source="message").require("read")),
):
    d = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    return d


@router.patch("/messages/{message_id}", response_model=dict)
async def update_message(
    message_id: str,
    payload: MessageUpdate,
    auth=Depends(IncidentAuth(id_source="message").require("write")),
):
    existing = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    if existing.get("finalisiert"):
        raise HTTPException(
            status_code=409, detail="Finalisierte Eintraege koennen nicht geaendert werden"
        )
    if existing.get("quelle") == "system":
        raise HTTPException(status_code=409, detail="Systemeintraege sind unveraenderlich")

    upd = payload.model_dump(exclude_none=True)
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    upd["updated_at"] = iso(now_utc())

    return await db.messages.find_one_and_update(
        {"id": message_id},
        {"$set": upd},
        return_document=True,
        projection={"_id": 0},
    )


@router.post("/messages/{message_id}/ack", response_model=dict)
async def ack_message(
    message_id: str,
    by: Optional[str] = None,
    auth=Depends(IncidentAuth(id_source="message").require("write")),
):
    result = await db.messages.find_one_and_update(
        {"id": message_id},
        {"$set": {"quittiert_at": iso(now_utc()), "quittiert_von": by or "Einsatzleiter"}},
        return_document=True,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    return result


@router.post("/messages/{message_id}/confirm", response_model=dict)
async def confirm_message(
    message_id: str,
    payload: MessageConfirm,
    auth=Depends(IncidentAuth(id_source="message").require("write")),
):
    existing = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    return await db.messages.find_one_and_update(
        {"id": message_id},
        {
            "$set": {
                "bestaetigt_at": iso(now_utc()),
                "bestaetigt_von": payload.bestaetigt_von or "Einsatzleiter",
            }
        },
        return_document=True,
        projection={"_id": 0},
    )


@router.post("/messages/{message_id}/finalize", response_model=dict)
async def finalize_message(
    message_id: str,
    by: Optional[str] = None,
    auth=Depends(IncidentAuth(id_source="message").require("assign_roles")),
):
    """Sperrt Eintrag gegen weitere Aenderungen – nur EL oder Admin."""
    existing = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    if existing.get("finalisiert"):
        return existing
    return await db.messages.find_one_and_update(
        {"id": message_id},
        {
            "$set": {
                "finalisiert": True,
                "finalisiert_at": iso(now_utc()),
                "finalisiert_von": by or existing.get("erfasst_von", "System"),
            }
        },
        return_document=True,
        projection={"_id": 0},
    )


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message(
    message_id: str,
    auth=Depends(IncidentAuth(id_source="message").require("write")),
):
    existing = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    if existing.get("finalisiert"):
        raise HTTPException(
            status_code=409, detail="Finalisierte Eintraege koennen nicht geloescht werden"
        )
    if existing.get("quelle") == "system":
        raise HTTPException(
            status_code=409, detail="Systemeintraege koennen nicht geloescht werden"
        )
    await db.messages.delete_one({"id": message_id})
    return None
