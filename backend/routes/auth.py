"""Authentication routes: login, refresh, me, logout.

Security fixes vs. original:
- Refresh token is SHA-256 hashed before DB insert
- /refresh checks that token hash exists in DB (revocation support)
- /logout deletes the token hash from DB
- JWT role comes from user.role directly (not flattened to admin/user)
"""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException

from core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    _hash_refresh_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    verify_password,
)
from core.db import db
from models.user import AuthUserOut, LoginRequest, RefreshRequest, TokenPair, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest):
    doc = await db.users.find_one({"username": payload.username}, {"_id": 0})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        # Unified message prevents username enumeration
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")

    if not doc.get("is_active", True):
        raise HTTPException(status_code=403, detail="Benutzerkonto ist deaktiviert")

    user_id: str = doc["id"]
    role: str = doc.get("role", "user")  # FIX: use actual role, not flattened

    access = create_access_token(user_id, role)
    refresh = create_refresh_token(user_id)
    token_hash = _hash_refresh_token(refresh)  # FIX: hash before storing

    await db.refresh_tokens.insert_one(
        {
            "user_id": user_id,
            "token_hash": token_hash,
            "created_at": dt.datetime.now(dt.timezone.utc),
        }
    )

    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest):
    payload_data = decode_token(payload.refresh_token, "refresh")
    user_id: str = payload_data.get("sub")

    # FIX: verify the token hash exists in DB (not revoked)
    token_hash = _hash_refresh_token(payload.refresh_token)
    stored = await db.refresh_tokens.find_one({"user_id": user_id, "token_hash": token_hash})
    if not stored:
        raise HTTPException(status_code=401, detail="Refresh-Token ungültig oder widerrufen")

    doc = await db.users.find_one({"id": user_id, "is_active": True}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")

    role: str = doc.get("role", "user")  # FIX: actual role
    new_access = create_access_token(user_id, role)
    new_refresh = create_refresh_token(user_id)
    new_hash = _hash_refresh_token(new_refresh)

    # Rotate: delete old token, insert new one (prevents replay attacks)
    await db.refresh_tokens.delete_one({"token_hash": token_hash})
    await db.refresh_tokens.insert_one(
        {
            "user_id": user_id,
            "token_hash": new_hash,
            "created_at": dt.datetime.now(dt.timezone.utc),
        }
    )

    return TokenPair(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=AuthUserOut)
async def me(user: UserOut = Depends(get_current_user)):
    return AuthUserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,  # FIX: pass actual role
        can_create_incidents=user.can_create_incidents,
    )


@router.post("/logout")
async def logout(
    payload: RefreshRequest,
    user: UserOut = Depends(get_current_user),
):
    """Revoke the refresh token so it can no longer be used."""
    token_hash = _hash_refresh_token(payload.refresh_token)
    await db.refresh_tokens.delete_many({"user_id": user.id, "token_hash": token_hash})
    return {"message": "Abgemeldet"}
