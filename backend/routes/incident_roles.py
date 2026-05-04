"""Incident role assignment routes.

EL can assign FA, AL, Dokumentation roles within their incident.
Admin can assign any role including EL.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user, UserOut
from core.db import db
from core.permissions import CAN_ASSIGN, IncidentAuth
from core.time import now_utc
from models.user import IncidentRole, IncidentRoleCreate, IncidentRoleOut, IncidentRoleUpdate

router = APIRouter(prefix="/api/incidents", tags=["incident-roles"])


@router.get("/{incident_id}/roles", response_model=List[IncidentRoleOut])
async def list_incident_roles(
    incident_id: str,
    auth=Depends(IncidentAuth().require("read")),
):
    cursor = db.incident_roles.find({"incident_id": incident_id}, {"_id": 0})
    return await cursor.to_list(500)


@router.post("/{incident_id}/roles", response_model=IncidentRoleOut, status_code=201)
async def assign_role(
    incident_id: str,
    payload: IncidentRoleCreate,
    auth=Depends(IncidentAuth().require("assign_roles")),
):
    user: UserOut = auth.user

    target = await db.users.find_one(
        {"id": payload.user_id, "is_active": True}, {"_id": 0, "id": 1}
    )
    if not target:
        raise HTTPException(status_code=404, detail="Zielbenutzer nicht gefunden")

    if user.role != "admin":
        allowed = CAN_ASSIGN.get(auth.role, [])
        if payload.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Rolle '{payload.role}' darf nicht vergeben werden",
            )

    # Replace existing role for this user in this incident
    await db.incident_roles.delete_many(
        {"user_id": payload.user_id, "incident_id": incident_id}
    )

    role = IncidentRole(
        incident_id=incident_id,
        user_id=payload.user_id,
        role=payload.role,
        abschnitt_id=payload.abschnitt_id,
        assigned_by=user.id,
    )
    doc = role.model_dump()
    await db.incident_roles.insert_one(doc)
    return IncidentRoleOut(**doc)


@router.patch("/{incident_id}/roles/{role_id}", response_model=IncidentRoleOut)
async def update_role(
    incident_id: str,
    role_id: str,
    payload: IncidentRoleUpdate,
    auth=Depends(IncidentAuth().require("assign_roles")),
):
    user: UserOut = auth.user
    existing = await db.incident_roles.find_one(
        {"id": role_id, "incident_id": incident_id}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Rolle nicht gefunden")

    if user.role != "admin":
        allowed = CAN_ASSIGN.get(auth.role, [])
        new_role = payload.role or existing["role"]
        if new_role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Rolle '{new_role}' darf nicht vergeben werden",
            )

    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Keine Änderungen")

    result = await db.incident_roles.find_one_and_update(
        {"id": role_id, "incident_id": incident_id},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )
    return IncidentRoleOut(**result)


@router.delete("/{incident_id}/roles/{role_id}", status_code=204)
async def remove_role(
    incident_id: str,
    role_id: str,
    auth=Depends(IncidentAuth().require("assign_roles")),
):
    result = await db.incident_roles.delete_one(
        {"id": role_id, "incident_id": incident_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rolle nicht gefunden")
    return None


@router.post("/{incident_id}/transfer-el")
async def transfer_el_role(
    incident_id: str,
    payload: IncidentRoleCreate,
    auth=Depends(IncidentAuth().require("assign_roles")),
):
    """Transfer EL role to another user. Current EL loses EL status."""
    new_el = await db.users.find_one(
        {"id": payload.user_id, "is_active": True},
        {"_id": 0, "id": 1, "can_create_incidents": 1},
    )
    if not new_el:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if not new_el.get("can_create_incidents"):
        raise HTTPException(
            status_code=403, detail="Benutzer hat keine EL-Berechtigung (can_create_incidents)"
        )

    await db.incidents.update_one(
        {"id": incident_id},
        {"$set": {"el_user_id": payload.user_id, "updated_at": now_utc()}},
    )
    await db.incident_roles.delete_many(
        {"user_id": payload.user_id, "incident_id": incident_id}
    )

    return {"message": "EL-Rolle übertragen", "new_el_user_id": payload.user_id}
