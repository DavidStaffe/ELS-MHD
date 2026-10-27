"""Read-only update capability endpoint.

The web app must never expose Docker or host commands through FastAPI.
An independent privileged host agent and real administrator authorization
are prerequisites for activating update and rollback operations.
"""
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/system/updates", tags=["system-updates"])

@router.get("/status")
async def update_status():
    return {
        "configured": False,
        "state": "not_configured",
        "update_available": None,
        "running_version": None,
        "available_version": None,
        "can_install": False,
        "can_rollback": False,
        "message": "Updateverwaltung noch nicht mit einem geschützten Host-Dienst verbunden.",
    }

@router.get("/check")
async def check_updates():
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Sichere Updateprüfung noch nicht eingerichtet.",
    )

@router.post("/apply")
async def apply_update():
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Updateinstallation gesperrt, bis Administratorauthentifizierung und Host-Dienst eingerichtet sind.",
    )

@router.post("/rollback")
async def rollback_update():
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Rollback gesperrt, bis Administratorauthentifizierung und Host-Dienst eingerichtet sind.",
    )
