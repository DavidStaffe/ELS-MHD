"""Narrow Unix-socket proxy. No host commands or Docker access in FastAPI."""

import asyncio
import json
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from core.admin import require_admin, audit

router = APIRouter(prefix="/api/system/updates", tags=["system-updates"])


async def agent(action, **values):
    path = os.environ.get("ELS_UPDATE_SOCKET")
    if not path:
        raise HTTPException(503, "Geschützter Host-Dienst ist nicht eingerichtet.")
    writer = None
    try:
        async with asyncio.timeout(10):
            reader, writer = await asyncio.open_unix_connection(path, limit=32768)
            writer.write(json.dumps({"action": action, **values}).encode() + b"\n")
            await writer.drain()
            result = json.loads(await reader.readline())
        if not result["ok"]:
            raise HTTPException(409, result["error"])
        return result["data"]
    except (OSError, TimeoutError, ValueError, KeyError):
        raise HTTPException(
            503,
            "Host-Dienst nicht erreichbar. Status erneut prüfen; nicht mehrfach starten.",
        ) from None
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: SecretStr = Field(max_length=1024)
    release_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    version: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")


@router.get("/status")
async def update_status():
    if not os.environ.get("ELS_UPDATE_SOCKET"):
        return {
            "configured": False,
            "state": "not_configured",
            "can_install": False,
            "can_rollback": False,
            "message": "Geschützter Host-Dienst ist nicht eingerichtet.",
        }
    return await agent("status")


@router.get("/check")
async def check_updates():
    return await agent("check")


async def start(action, payload):
    await audit("system." + action, "requested")
    try:
        result = await agent(
            action,
            password=payload.password.get_secret_value(),
            version=payload.version,
            release_id=payload.release_id,
        )
    except Exception:
        await audit("system." + action, "failed")
        raise
    await audit("system." + action, "accepted")
    return result


@router.post("/apply", dependencies=[Depends(require_admin)], status_code=202)
async def apply_update(payload: Approval):
    return await start("apply", payload)


@router.post("/rollback", dependencies=[Depends(require_admin)], status_code=202)
async def rollback_update(payload: Approval):
    return await start("rollback", payload)
