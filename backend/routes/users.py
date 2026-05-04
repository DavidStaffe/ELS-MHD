"""User management routes (Admin only)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from core.auth import hash_password, require_admin
from core.db import db
from core.time import now_utc
from models.user import User, UserCreate, UserListOut, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserListOut])
async def list_users(admin=Depends(require_admin)):
    cursor = db.users.find({}, {"_id": 0, "password_hash": 0})
    return await cursor.to_list(1000)


@router.post("", response_model=UserOut, status_code=201)
async def create_user(payload: UserCreate, admin=Depends(require_admin)):
    if await db.users.find_one({"username": payload.username}):
        raise HTTPException(status_code=409, detail="Benutzername bereits vergeben")

    user = User(
        username=payload.username,
        display_name=payload.display_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        can_create_incidents=payload.can_create_incidents,
    )
    doc = user.model_dump()
    await db.users.insert_one(doc)
    return UserOut(**doc)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: str, admin=Depends(require_admin)):
    doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return UserOut(**doc)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: str, payload: UserUpdate, admin=Depends(require_admin)):
    existing = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Keine Änderungen angegeben")

    if "password" in update:
        update["password_hash"] = hash_password(update.pop("password"))

    update["updated_at"] = now_utc()

    result = await db.users.find_one_and_update(
        {"id": user_id},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )
    return UserOut(**result)


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: str, admin=Depends(require_admin)):
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    await db.incident_roles.delete_many({"user_id": user_id})
    return None
