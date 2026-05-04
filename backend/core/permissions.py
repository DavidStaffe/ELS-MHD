"""Incident-level permission system.

Roles within an incident:
  el            – Einsatzleiter (full control within incident)
  fa            – Führungsassistent (read/write, no role assignment)
  al            – Abschnittsleiter (read/write own Abschnitt only)
  dokumentation – read-only

System role 'admin' always bypasses incident-level checks.

IncidentAuth supports two ID sources:
  - id_source='incident'  (default): expects {incident_id} path param
  - id_source='abschnitt' : looks up incident_id from abschnitte collection
  - id_source='resource'  : looks up incident_id from resources collection
  - id_source='transport' : looks up incident_id from transports collection
  - id_source='message'   : looks up incident_id from messages collection
  - id_source='patient'   : looks up incident_id from patients collection
"""
from dataclasses import dataclass
from typing import Literal, Optional

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

IdSource = Literal["incident", "abschnitt", "resource", "transport", "message", "patient"]

# Maps id_source to (collection, field_name_of_incident_id)
_COLLECTION_MAP: dict[str, tuple[str, str]] = {
    "abschnitt": ("abschnitte",    "incident_id"),
    "resource":  ("resources",     "incident_id"),
    "transport": ("transports",    "incident_id"),
    "message":   ("messages",      "incident_id"),
    "patient":   ("patients",      "incident_id"),
}


@dataclass
class IncidentAuthResult:
    user: UserOut
    role: Optional[IncidentRoleType]  # None if admin without explicit role
    is_el: bool
    incident_id: str


async def _get_role_doc(user_id: str, incident_id: str) -> Optional[dict]:
    return await db.incident_roles.find_one(
        {"user_id": user_id, "incident_id": incident_id}, {"_id": 0}
    )


async def _resolve_incident_id(id_source: IdSource, resource_id: str) -> str:
    """Resolve an incident_id by looking up a sub-resource by its id."""
    if id_source == "incident":
        return resource_id
    collection_name, field = _COLLECTION_MAP[id_source]
    collection = getattr(db, collection_name)
    doc = await collection.find_one({"id": resource_id}, {"_id": 0, field: 1})
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"{id_source.capitalize()} nicht gefunden",
        )
    return doc[field]


class IncidentAuth:
    """FastAPI dependency factory for incident-level permission checks.

    Usage:
        # For incident-scoped routes with {incident_id} path param:
        auth = Depends(IncidentAuth().require("write"))

        # For routes with a sub-resource ID (e.g. {transport_id}):
        auth = Depends(IncidentAuth(id_source="transport").require("read"))
    """

    def __init__(self, id_source: IdSource = "incident"):
        self.id_source = id_source

    def require(self, permission: str):
        id_source = self.id_source

        async def _check(
            incident_id: Optional[str] = None,
            abschnitt_id: Optional[str] = None,
            resource_id: Optional[str] = None,
            transport_id: Optional[str] = None,
            message_id: Optional[str] = None,
            patient_id: Optional[str] = None,
            user: UserOut = Depends(get_current_user),
        ) -> IncidentAuthResult:
            # Pick the right path param based on id_source
            raw_id = {
                "incident":  incident_id,
                "abschnitt": abschnitt_id,
                "resource":  resource_id,
                "transport": transport_id,
                "message":   message_id,
                "patient":   patient_id,
            }.get(id_source)

            if not raw_id:
                raise HTTPException(status_code=400, detail="Fehlende ID im Pfad")

            resolved_incident_id = await _resolve_incident_id(id_source, raw_id)

            # Admins bypass all incident-level checks
            if user.role == "admin":
                return IncidentAuthResult(
                    user=user, role=None, is_el=True, incident_id=resolved_incident_id
                )

            # Check if user is EL of this incident
            incident = await db.incidents.find_one(
                {"id": resolved_incident_id, "el_user_id": user.id},
                {"_id": 0, "id": 1},
            )
            if incident:
                return IncidentAuthResult(
                    user=user, role="el", is_el=True, incident_id=resolved_incident_id
                )

            # Check incident role
            role_doc = await _get_role_doc(user.id, resolved_incident_id)
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
                incident_id=resolved_incident_id,
            )

        return _check
