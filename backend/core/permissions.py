"""Incident-level permission system.

Roles within an incident:
  el           – Einsatzleiter (full control within incident)
  fa           – Führungsassistent (read/write, no role assignment)
  al           – Abschnittsleiter (read/write own Abschnitt only)
  dokumentation – read-only

System role 'admin' always bypasses incident-level checks.
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException

from core.auth import get_current_user
from core.db import db
from models.user import UserOut, IncidentRoleType

# Which incident roles can assign which roles
CAN_ASSIGN: dict[str, list[str]] = {
    "el": ["fa", "al", "dokumentation"],
    "fa": [],
    "al": [],
    "dokumentation": [],
}

# Minimum role required per permission level
PERMISSION_LEVELS: dict[str, set[str]] = {
    "read":         {"el", "fa", "al", "dokumentation"},
    "write":        {"el", "fa", "al"},
    "assign_roles": {"el"},
}


@dataclass
class IncidentAuthResult:
    user: UserOut
    role: Optional[IncidentRoleType]  # None if admin without explicit role
    is_el: bool


async def _get_role_doc(user_id: str, incident_id: str) -> Optional[dict]:
    return await db.incident_roles.find_one(
        {"user_id": user_id, "incident_id": incident_id}, {"_id": 0}
    )


class IncidentAuth:
    """FastAPI dependency factory for incident-level permission checks.

    Usage:
        auth: IncidentAuthResult = Depends(IncidentAuth().require("write"))
    """

    def require(self, permission: str):
        async def _check(
            incident_id: str,
            user: UserOut = Depends(get_current_user),
        ) -> IncidentAuthResult:
            # Admins bypass all incident-level checks
            if user.role == "admin":
                return IncidentAuthResult(user=user, role=None, is_el=True)

            # Check if user is EL of this incident
            incident = await db.incidents.find_one(
                {"id": incident_id, "el_user_id": user.id}, {"_id": 0, "id": 1}
            )
            if incident:
                return IncidentAuthResult(user=user, role="el", is_el=True)

            # Check incident role
            role_doc = await _get_role_doc(user.id, incident_id)
            if not role_doc:
                raise HTTPException(
                    status_code=403,
                    detail="Kein Zugriff auf diesen Einsatz",
                )

            role: IncidentRoleType = role_doc["role"]
            allowed_roles = PERMISSION_LEVELS.get(permission, set())

            if role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Berechtigung '{permission}' erforderlich (aktuelle Rolle: {role})",
                )

            return IncidentAuthResult(
                user=user,
                role=role,
                is_el=False,
            )

        return _check
