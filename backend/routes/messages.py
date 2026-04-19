"""Messages routes."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from core.db import db
from core.time import iso, now_utc
from models import MessageCreate

router = APIRouter(prefix="/api", tags=["messages"])


@router.get("/incidents/{incident_id}/messages", response_model=List[dict])
async def list_messages(incident_id: str, open_only: bool = False):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    query: dict = {"incident_id": incident_id}
    if open_only:
        query["quittiert_at"] = None
    return await db.messages.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/incidents/{incident_id}/messages", response_model=dict, status_code=201)
async def create_message(incident_id: str, payload: MessageCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    doc = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        **payload.model_dump(exclude_none=True),
        "quittiert_at": None,
        "quittiert_von": None,
        "created_at": iso(now_utc()),
    }
    await db.messages.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.post("/messages/{message_id}/ack", response_model=dict)
async def ack_message(message_id: str, by: Optional[str] = None):
    result = await db.messages.find_one_and_update(
        {"id": message_id},
        {"$set": {"quittiert_at": iso(now_utc()), "quittiert_von": by or "Einsatzleiter"}},
        return_document=True, projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    return result


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message(message_id: str):
    r = await db.messages.delete_one({"id": message_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    return None
