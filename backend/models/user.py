"""Pydantic models for User and IncidentRole domain objects."""
import uuid
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

from core.time import now_utc

SystemRole = Literal["admin", "user"]
IncidentRoleType = Literal["el", "fa", "al", "dokumentation"]


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    display_name: str
    email: Optional[str] = None
    password_hash: str
    role: SystemRole = "user"
    can_create_incidents: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str
    email: Optional[str] = None
    role: SystemRole
    can_create_incidents: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserListOut(BaseModel):
    id: str
    username: str
    display_name: str
    role: SystemRole
    can_create_incidents: bool
    is_active: bool


class AuthUserOut(BaseModel):
    """Minimal user info returned by /auth/me – safe for frontend."""
    id: str
    username: str
    display_name: str
    role: SystemRole
    can_create_incidents: bool


class UserCreate(BaseModel):
    username: str
    display_name: str
    email: Optional[str] = None
    password: str
    role: SystemRole = "user"
    can_create_incidents: bool = False


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[SystemRole] = None
    can_create_incidents: Optional[bool] = None
    is_active: Optional[bool] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# --- Incident Roles ---

class IncidentRole(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    user_id: str
    role: IncidentRoleType
    abschnitt_id: Optional[str] = None
    assigned_by: str
    created_at: datetime = Field(default_factory=now_utc)


class IncidentRoleOut(BaseModel):
    id: str
    incident_id: str
    user_id: str
    role: IncidentRoleType
    abschnitt_id: Optional[str] = None
    assigned_by: str
    created_at: datetime


class IncidentRoleCreate(BaseModel):
    user_id: str
    role: IncidentRoleType
    abschnitt_id: Optional[str] = None


class IncidentRoleUpdate(BaseModel):
    role: Optional[IncidentRoleType] = None
    abschnitt_id: Optional[str] = None
