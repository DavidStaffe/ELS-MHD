"""Incidents routes – secured with RBAC.

Permission matrix:
  GET  /incidents              – authenticated (filtered by role)
  POST /incidents              – can_create_incidents flag
  POST /incidents/demo         – admin only
  GET  /incidents/stream       – token query-param (SSE compatible)
  GET  /incidents/{id}         – read
  PATCH /incidents/{id}        – write
  PATCH /incidents/{id}/meta   – write
  DELETE /incidents/{id}       – admin only
"""
import asyncio
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from core.auth import get_current_user, require_admin, decode_token
from core.db import db
from core.permissions import IncidentAuth
from core.time import iso, now_utc, serialize_datetimes
from core.types import IncidentStatus
from models import Incident, IncidentCreate, IncidentMetaPatch, IncidentUpdate
from models.user import UserOut
from services.demo import create_demo_incident as _svc_create_demo
from services.realtime import (
    publish_incident_event,
    subscribe_incidents,
    unsubscribe_incidents,
)
from services.seeds import seed_default_resources

router = APIRouter(prefix="/api", tags=["incidents"])

_INC_DATES = ("start_at", "end_at", "created_at", "updated_at")


def _ser_inc(doc: dict) -> dict:
    return serialize_datetimes(doc, _INC_DATES)


@router.get("/", include_in_schema=False)
async def root():
    return {"message": "ELS MHD API", "version": "1.0.0"}


@router.get("/meta")
async def meta():
    return {
        "app": "ELS MHD",
        "name": "Einsatzleitsystem Malteser Hilfsdienst",
        "version": "1.0.0",
        "step": "01-12",
    }


@router.get("/incidents", response_model=List[dict])
async def list_incidents(
    status: Optional[IncidentStatus] = None,
    demo: Optional[bool] = None,
    user: UserOut = Depends(get_current_user),
):
    query: dict = {}
    if status:
        query["status"] = status
    if demo is not None:
        query["demo"] = demo

    # Admins see everything; others see only their incidents
    if user.role != "admin":
        role_incidents = await db.incident_roles.find(
            {"user_id": user.id}, {"incident_id": 1}
        ).to_list(None)
        incident_ids = [r["incident_id"] for r in role_incidents]

        el_incidents = await db.incidents.find(
            {"el_user_id": user.id}, {"id": 1}
        ).to_list(None)
        incident_ids += [i["id"] for i in el_incidents]

        if not incident_ids:
            return []
        query["id"] = {"$in": list(set(incident_ids))}

    cursor = db.incidents.find(query, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(500)


@router.get("/incidents/stream")
async def stream_incidents(
    request: Request,
    token: Optional[str] = Query(default=None, description="Access-Token für SSE-Auth"),
):
    """Server-Sent Events stream for incident list changes.

    SSE cannot send Authorization headers in all browsers, so we accept
    the access token as a query parameter. Validate it the same way.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Token erforderlich (?token=...)")
    try:
        decode_token(token, "access")
    except HTTPException:
        raise HTTPException(status_code=401, detail="Ungültiges oder abgelaufenes Token")

    q = subscribe_incidents()

    async def event_gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=20.0)
                    payload = json.dumps(evt)
                    yield f"event: incident\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            unsubscribe_incidents(q)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/incidents", response_model=dict, status_code=201)
async def create_incident(
    payload: IncidentCreate,
    user: UserOut = Depends(get_current_user),
):
    if user.role != "admin" and not user.can_create_incidents:
        raise HTTPException(
            status_code=403, detail="Keine Berechtigung zum Anlegen von Einsätzen"
        )

    obj = Incident(**payload.model_dump(exclude_none=True))
    if obj.status == "geplant":
        obj.start_at = None
    elif payload.start_at is None:
        obj.start_at = now_utc()

    # Automatically assign creator as EL
    obj.el_user_id = user.id

    doc = obj.model_dump()
    for k in _INC_DATES:
        if isinstance(doc.get(k), datetime):
            doc[k] = iso(doc[k])

    await db.incidents.insert_one(doc)
    await seed_default_resources(obj.id)
    out = _ser_inc(doc)
    await publish_incident_event(
        {
            "kind": "incident",
            "action": "created",
            "incident_id": out["id"],
            "ts": iso(now_utc()),
        }
    )
    return out


@router.post("/incidents/demo", response_model=dict, status_code=201)
async def create_demo_incident(admin=Depends(require_admin)):
    """Create a demo incident – admin only."""
    out = await _svc_create_demo()
    await publish_incident_event(
        {
            "kind": "incident",
            "action": "created",
            "incident_id": out["id"],
            "ts": iso(now_utc()),
        }
    )
    return out


@router.get("/incidents/{incident_id}", response_model=dict)
async def get_incident(
    incident_id: str,
    auth=Depends(IncidentAuth().require("read")),
):
    doc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    return doc


@router.patch("/incidents/{incident_id}", response_model=dict)
async def update_incident(
    incident_id: str,
    payload: IncidentUpdate,
    auth=Depends(IncidentAuth().require("write")),
):
    existing = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Keine Aenderungen angegeben")

    for k in ("start_at", "end_at"):
        if k in update and isinstance(update[k], datetime):
            update[k] = iso(update[k])

    update["updated_at"] = iso(now_utc())

    if update.get("status") == "operativ" and existing.get("status") == "geplant":
        if "start_at" not in update:
            update["start_at"] = iso(now_utc())
    if update.get("status") == "abgeschlossen":
        if not existing.get("end_at"):
            update["end_at"] = iso(now_utc())

    result = await db.incidents.find_one_and_update(
        {"id": incident_id},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )
    await publish_incident_event(
        {
            "kind": "incident",
            "action": "updated",
            "incident_id": result["id"],
            "ts": iso(now_utc()),
        }
    )
    return result


@router.patch("/incidents/{incident_id}/meta", response_model=dict)
async def patch_incident_meta(
    incident_id: str,
    payload: IncidentMetaPatch,
    auth=Depends(IncidentAuth().require("write")),
):
    data = payload.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")

    set_fields = {f"meta.{k}": v for k, v in data.items()}
    set_fields["updated_at"] = iso(now_utc())

    result = await db.incidents.find_one_and_update(
        {"id": incident_id},
        {"$set": set_fields},
        return_document=True,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    return result


@router.delete("/incidents/{incident_id}", status_code=204)
async def delete_incident(
    incident_id: str,
    admin=Depends(require_admin),
):
    """Hard-delete an incident and all related data – admin only."""
    result = await db.incidents.delete_one({"id": incident_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    await db.patients.delete_many({"incident_id": incident_id})
    await db.transports.delete_many({"incident_id": incident_id})
    await db.resources.delete_many({"incident_id": incident_id})
    await db.messages.delete_many({"incident_id": incident_id})
    await db.abschnitte.delete_many({"incident_id": incident_id})
    await db.betten.delete_many({"incident_id": incident_id})
    await db.report_versions.delete_many({"incident_id": incident_id})
    await db.incident_roles.delete_many({"incident_id": incident_id})

    await publish_incident_event(
        {
            "kind": "incident",
            "action": "deleted",
            "incident_id": incident_id,
            "ts": iso(now_utc()),
        }
    )
    return None
