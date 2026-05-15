"""Resources routes."""
from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, HTTPException

from core.db import db
from core.time import iso, now_utc
from models import ResourceCreate, ResourceUpdate
from services.fms_audit import record_fms_change

router = APIRouter(prefix="/api", tags=["resources"])


@router.get("/incidents/{incident_id}/resources", response_model=List[dict])
async def list_resources(incident_id: str, typ: Optional[str] = None, status: Optional[str] = None):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    query: dict = {"incident_id": incident_id}
    if typ:
        query["typ"] = {"$in": [v.strip() for v in typ.split(",") if v.strip()]}
    if status:
        query["status"] = {"$in": [v.strip() for v in status.split(",") if v.strip()]}
    return await db.resources.find(query, {"_id": 0}).sort([("typ", 1), ("name", 1)]).to_list(500)


@router.post("/incidents/{incident_id}/resources", response_model=dict, status_code=201)
async def create_resource(incident_id: str, payload: ResourceCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    now = now_utc()
    data = payload.model_dump(exclude_unset=True)
    doc = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "name": data["name"],
        "typ": data["typ"],
        "kategorie": data.get("kategorie", "sonstiges"),
        "status": data.get("status", "verfuegbar"),
        "notiz": data.get("notiz", ""),
        "abschnitt_id": data.get("abschnitt_id"),
        "lat": data.get("lat"),
        "lng": data.get("lng"),
        "divera_id": data.get("divera_id"),
        "fms_status": data.get("fms_status"),
        "created_at": iso(now),
        "updated_at": iso(now),
    }
    await db.resources.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.patch("/resources/{resource_id}", response_model=dict)
async def update_resource(resource_id: str, payload: ResourceUpdate):
    # exclude_unset preserves explicit nulls so clients can clear lat/lng etc.
    upd = payload.model_dump(exclude_unset=True)
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    upd["updated_at"] = iso(now_utc())
    # Read existing for audit comparison
    before = await db.resources.find_one({"id": resource_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Ressource nicht gefunden")
    res = await db.resources.find_one_and_update(
        {"id": resource_id}, {"$set": upd},
        return_document=True, projection={"_id": 0},
    )
    # Manual FMS change → audit (skip if divera_id linked – Divera-sync logs separately)
    if "fms_status" in upd and not before.get("divera_id"):
        await record_fms_change(
            incident_id=before["incident_id"],
            resource_id=resource_id,
            resource_name=before.get("name", ""),
            vehicle_name=None,
            divera_id=None,
            from_fms=before.get("fms_status"),
            to_fms=upd.get("fms_status"),
            from_status=before.get("status"),
            to_status=res.get("status"),
            source="manual",
        )
    return res


@router.delete("/resources/{resource_id}", status_code=204)
async def delete_resource(resource_id: str):
    r = await db.resources.delete_one({"id": resource_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ressource nicht gefunden")
    return None


@router.get("/incidents/{incident_id}/fms-events")
async def list_fms_events(
    incident_id: str,
    resource_id: Optional[str] = None,
    limit: int = 200,
):
    """FMS-Audit-Trail: alle Status-Aenderungen pro Incident (neuste zuerst)."""
    query = {"incident_id": incident_id}
    if resource_id:
        query["resource_id"] = resource_id
    limit = max(1, min(limit, 1000))
    events = await db.fms_events.find(query, {"_id": 0}).sort("ts", -1).to_list(limit)
    return events
