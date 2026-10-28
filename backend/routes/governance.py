"""Incident appointments, closure, archive grants and versioned corrections.

Assignments and their history share one Mongo document. Compare-and-swap prevents
lost appointments and enforces all leadership limits without replica-set support.
"""

from datetime import timedelta
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict, field_validator
from core.identity import (
    db,
    identity,
    has,
    require,
    role_for,
    incident_access,
    medical,
    audit,
    ROLES,
)
from core.time import now_utc, iso

router = APIRouter(prefix="/api", tags=["governance"])


@router.get("/leadership-candidates")
async def leadership_candidates(request: Request):
    user = await identity(request)
    if not any(
        has(user, p)
        for p in ("incidents.create", "incidents.roles.assign", "incidents.reopen")
    ):
        raise HTTPException(403, "Keine Ernennungs-/Erstellberechtigung.")
    return await db.users.find(
        {"active": True, "eligible": "EL"}, {"_id": 0, "id": 1, "display_name": 1}
    ).to_list(10000)


@router.get("/archive-catalog")
async def archive_catalog(request: Request):
    user = await identity(request)
    if not user.get("admin"):
        require(user, "archives.manage")
    # Administrative identifiers only. This grants no archive content access.
    return await db.incidents.find(
        {"status": "abgeschlossen"}, {"_id": 0, "id": 1, "name": 1, "status": 1}
    ).to_list(None)


@router.get("/archive-candidates")
async def archive_candidates(request: Request):
    user = await identity(request)
    if not user.get("admin"):
        require(user, "archives.manage")
    return await db.users.find(
        {"active": True}, {"_id": 0, "id": 1, "display_name": 1}
    ).to_list(None)


@router.get("/incidents/{incident_id}/role-candidates")
async def role_candidates(incident_id: str, request: Request):
    user, inc = await context(request, incident_id, read=False)
    role = role_for(user, inc).get("role")
    if role not in {"EL", "FueAss"} and not has(user, "incidents.roles.assign"):
        raise HTTPException(403, "Keine Rollenverwaltung.")
    return await db.users.find(
        {"active": True}, {"_id": 0, "id": 1, "display_name": 1, "eligible": 1}
    ).to_list(None)


class Reason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Begründung erforderlich.")
        return value.strip()


async def context(request, incident_id, *, read=True):
    user = await identity(request)
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(404, "Einsatz fehlt.")
    if read and not await incident_access(user, inc):
        raise HTTPException(403, "Leseberechtigung fehlt.")
    return user, inc


def change_event(user, inc, action, reason, before, after):
    return {
        "at": iso(now_utc()),
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": role_for(user, inc).get("role"),
        "permissions": sorted(user.get("permissions", [])),
        "action": action,
        "reason": reason.strip(),
        "before": before,
        "after": after,
    }


async def update_incident(inc, changes, event):
    version = inc.get("security_version", 0)
    selector = (
        {"id": inc["id"], "security_version": version}
        if version
        else {
            "id": inc["id"],
            "$or": [{"security_version": 0}, {"security_version": {"$exists": False}}],
        }
    )
    result = await db.incidents.update_one(
        selector,
        {
            "$set": changes,
            "$inc": {"security_version": 1},
            "$push": {"security_history": event},
        },
    )
    if not result.modified_count:
        raise HTTPException(409, "Einsatz wurde geändert. Bitte neu laden.")


class Appointment(Reason):
    user_id: str
    role: str | None = None
    section_id: str | None = None
    supports: str | None = None
    resource_id: str | None = None


def validate_assignments(assignments):
    leaders = [a for a in assignments.values() if a["role"] == "EL"]
    if len(leaders) != 1:
        raise HTTPException(409, "Genau eine EL ist erforderlich.")
    central = [
        a
        for a in assignments.values()
        if a["role"] == "FueAss" and a.get("supports") == "EL"
    ]
    if len(central) > 2:
        raise HTTPException(409, "Maximal zwei FüAss der EL.")
    sections = {
        a.get("section_id") for a in assignments.values() if a.get("section_id")
    }
    for section in sections:
        for role in ("AL", "FueAss"):
            if (
                sum(
                    a["role"] == role and a.get("section_id") == section
                    for a in assignments.values()
                )
                > 1
            ):
                raise HTTPException(409, "Abschnittsführung bereits besetzt.")
    for a in assignments.values():
        if a["role"] == "FueAss" and a.get("supports") not in {"EL", "AL"}:
            raise HTTPException(422, "FüAss muss ausdrücklich EL oder AL unterstützen.")
        if a["role"] == "FueAss" and a.get("supports") == "EL" and a.get("section_id"):
            raise HTTPException(
                422, "Zentrale FüAss darf keinem Abschnitt zugeordnet sein."
            )
        if a["role"] == "FueAss" and a.get("supports") != "EL":
            if not a.get("section_id") or not any(
                b["role"] == "AL" and b.get("section_id") == a["section_id"]
                for b in assignments.values()
            ):
                raise HTTPException(
                    409, "FüAss benötigt eine aktive zugeordnete Abschnittsleitung."
                )


@router.put("/incidents/{incident_id}/assignments")
async def appoint(incident_id: str, payload: Appointment, request: Request):
    user, inc = await context(request, incident_id, read=False)
    if inc["status"] == "abgeschlossen":
        raise HTTPException(409, "Archiv bleibt geschlossen.")
    own = role_for(user, inc).get("role")
    assignments = dict(inc.get("assignments", {}))
    old = assignments.get(payload.user_id, {})
    affected = {old.get("role"), payload.role} - {None}
    if affected & {"EL", "FueAss"}:
        require(user, "incidents.roles.assign")
    if affected & {"AL", "Dokumentar"}:
        if own != "EL":
            raise HTTPException(403, "Nur EL ernennt AL und Dokumentar.")
    if (affected & {"Helfer"} or not affected) and own not in {"EL", "FueAss"}:
        raise HTTPException(403, "Nur EL/FüAss ordnet Helfer zu.")
    target_query = {"id": payload.user_id}
    if payload.role:
        target_query["active"] = True
    target = await db.users.find_one(target_query)
    if not target:
        raise HTTPException(422, "Aktives Benutzerkonto erforderlich.")
    if payload.role:
        if payload.role not in ROLES or (
            payload.role != "Helfer" and payload.role not in target.get("eligible", [])
        ):
            raise HTTPException(422, "Eignungsfreigabe fehlt.")
        if payload.role == "AL" and not payload.section_id:
            raise HTTPException(422, "Abschnitt fehlt.")
        if payload.section_id and not await db.abschnitte.find_one(
            {"id": payload.section_id, "incident_id": incident_id}
        ):
            raise HTTPException(422, "Abschnitt gehört nicht zum Einsatz.")
        if payload.role == "Helfer":
            if user["id"] == payload.user_id:
                raise HTTPException(403, "Keine Selbstzuordnung.")
            if not await db.resources.find_one(
                {"id": payload.resource_id, "incident_id": incident_id}
            ):
                raise HTTPException(422, "Ressource gehört nicht zum Einsatz.")
        if payload.role == "EL":
            assignments = {
                uid: a for uid, a in assignments.items() if a["role"] != "EL"
            }
        assignments[payload.user_id] = {
            "role": payload.role,
            "section_id": payload.section_id,
            "supports": payload.supports,
            "resource_id": payload.resource_id,
        }
    else:
        assignments.pop(payload.user_id, None)
    validate_assignments(assignments)
    await update_incident(
        inc,
        {"assignments": assignments},
        change_event(
            user,
            inc,
            "role.change",
            payload.reason,
            inc.get("assignments", {}),
            assignments,
        ),
    )
    return {"assignments": assignments}


class Support(Reason):
    supports: str
    section_id: str | None = None


@router.put("/incidents/{incident_id}/assistants/{user_id}/support")
async def assistant_support(
    incident_id: str, user_id: str, payload: Support, request: Request
):
    user, inc = await context(request, incident_id, read=False)
    if inc["status"] == "abgeschlossen":
        raise HTTPException(409, "Archiv bleibt geschlossen.")
    if role_for(user, inc).get("role") != "EL":
        require(user, "incidents.roles.assign")
    assignment = inc.get("assignments", {}).get(user_id)
    if not assignment or assignment["role"] != "FueAss":
        raise HTTPException(409, "Keine bestehende FüAss-Ernennung.")
    if payload.supports not in {"EL", "AL"}:
        raise HTTPException(422, "Unterstützung EL oder AL erforderlich.")
    if payload.supports == "AL" and not await db.abschnitte.find_one(
        {"id": payload.section_id, "incident_id": incident_id}
    ):
        raise HTTPException(422, "Abschnitt fehlt.")
    assignments = dict(inc["assignments"])
    assignments[user_id] = {
        **assignment,
        "supports": payload.supports,
        "section_id": payload.section_id if payload.supports == "AL" else None,
    }
    validate_assignments(assignments)
    await update_incident(
        inc,
        {"assignments": assignments},
        change_event(
            user,
            inc,
            "assistant.support.change",
            payload.reason,
            inc["assignments"],
            assignments,
        ),
    )
    return {"assignments": assignments}


async def open_work(incident_id):
    result = {}
    for collection, query in {
        "patients": {"status": {"$nin": ["uebergeben", "entlassen"]}},
        "transports": {"status": {"$ne": "abgeschlossen"}},
        "resources": {"bound_patient_id": {"$nin": [None, ""]}},
    }.items():
        result[collection] = (
            await db[collection]
            .find(
                {"incident_id": incident_id, **query},
                {"_id": 0, "id": 1, "status": 1, "bound_patient_id": 1},
            )
            .to_list(None)
        )
    result["dispositions"] = await db.patients.find(
        {
            "incident_id": incident_id,
            "status": {"$nin": ["uebergeben", "entlassen"]},
            "zugewiesene_ressource_id": {"$in": [None, ""]},
        },
        {"_id": 0, "id": 1},
    ).to_list(None)
    return result


@router.get("/incidents/{incident_id}/closure-preview")
async def closure_preview(incident_id: str, request: Request):
    user, inc = await context(request, incident_id, read=False)
    if role_for(user, inc).get("role") != "EL":
        require(user, "incidents.close")
    return await open_work(incident_id)


class Close(Reason):
    confirm_open: bool = False


@router.post("/incidents/{incident_id}/close")
async def close(incident_id: str, payload: Close, request: Request):
    user, inc = await context(request, incident_id, read=False)
    is_el = role_for(user, inc).get("role") == "EL"
    if not is_el:
        require(user, "incidents.close")
    if inc["status"] == "abgeschlossen":
        raise HTTPException(409, "Bereits abgeschlossen.")
    snapshot = await open_work(incident_id)
    if any(snapshot.values()) and not payload.confirm_open:
        raise HTTPException(
            409,
            {"message": "Offene Vorgänge ausdrücklich bestätigen.", "open": snapshot},
        )
    previous_el = next(
        (uid for uid, a in inc.get("assignments", {}).items() if a["role"] == "EL"),
        None,
    )
    changes = {
        "status": "abgeschlossen",
        "end_at": iso(now_utc()),
        "last_el_id": previous_el,
        "closed_by": user["id"],
        "closed_personally_as_el": is_el,
        "inactive_assignments": inc.get("assignments", {}),
        "assignments": {},
        "closure_open_snapshot": snapshot,
    }
    await update_incident(
        inc,
        changes,
        change_event(
            user,
            inc,
            "incident.close",
            payload.reason,
            {"status": inc["status"]},
            changes,
        ),
    )
    return {"closed": True, "open": snapshot}


class Reopen(Reason):
    el_user_id: str | None = None


@router.post("/incidents/{incident_id}/reopen")
async def reopen(incident_id: str, payload: Reopen, request: Request):
    user, inc = await context(request, incident_id, read=False)
    if not has(user, "incidents.reopen") and not (
        inc.get("closed_personally_as_el")
        and inc.get("closed_by") == user["id"] == inc.get("last_el_id")
    ):
        raise HTTPException(403, "Keine Wiedereröffnungsberechtigung.")
    if inc["status"] != "abgeschlossen":
        raise HTTPException(409, "Einsatz ist bereits offen.")
    el_id = inc.get("last_el_id")
    target = await db.users.find_one({"id": el_id, "active": True, "eligible": "EL"})
    if not target:
        require(user, "incidents.roles.assign")
        el_id = payload.el_user_id
        target = await db.users.find_one(
            {"id": el_id, "active": True, "eligible": "EL"}
        )
    if not target:
        raise HTTPException(422, "Neue geeignete EL erforderlich.")
    changes = {
        "status": "operativ",
        "end_at": None,
        "assignments": {el_id: {"role": "EL"}},
    }
    await update_incident(
        inc,
        changes,
        change_event(
            user,
            inc,
            "incident.reopen",
            payload.reason,
            {"status": inc["status"]},
            changes,
        ),
    )
    return {"reopened": True, "el_user_id": el_id}


class Grant(Reason):
    user_id: str
    days: int = Field(default=30, ge=1, le=3650)
    revoke: bool = False


@router.put("/incidents/{incident_id}/archive-grants")
async def grant(incident_id: str, payload: Grant, request: Request):
    user, inc = await context(request, incident_id, read=False)
    if not user.get("admin"):
        require(user, "archives.manage")
    if inc["status"] != "abgeschlossen":
        raise HTTPException(409, "Nur für Archive.")
    if not await db.users.find_one({"id": payload.user_id, "active": True}):
        raise HTTPException(422, "Aktives Zielkonto erforderlich.")
    changes = {
        "incident_id": incident_id,
        "user_id": payload.user_id,
        "revoked": payload.revoke,
        "expires_at": iso(now_utc() + timedelta(days=payload.days)),
    }
    await audit(
        user,
        "archive.grant.change",
        incident_id=incident_id,
        reason=payload.reason,
        data=changes,
    )
    await db.archive_grants.update_one(
        {"incident_id": incident_id, "user_id": payload.user_id},
        {"$set": changes},
        upsert=True,
    )
    return changes


class Correction(Reason):
    changes: dict


@router.post("/incidents/{incident_id}/corrections/{kind}/{record_id}")
async def correct(
    incident_id: str, kind: str, record_id: str, payload: Correction, request: Request
):
    user, inc = await context(request, incident_id)
    if kind not in {"messages", "patients", "incidents"}:
        raise HTTPException(422, "Unbekannte Dokumentationsart.")
    selector = (
        {"id": incident_id}
        if kind == "incidents" and record_id == incident_id
        else {"id": record_id, "incident_id": incident_id}
    )
    record = await db[kind].find_one(selector, {"_id": 0})
    if not record:
        raise HTTPException(404, "Eintrag fehlt.")
    role = role_for(user, inc)
    archived = inc["status"] == "abgeschlossen"
    if archived:
        require(
            user,
            "archives.patients.correct" if kind == "patients" else "archives.correct",
        )
        if kind == "patients" and not medical(user, inc):
            raise HTTPException(403, "Medizinische Leseberechtigung fehlt.")
    elif kind != "messages":
        raise HTTPException(409, "Medizinische Korrektur hier nur im Archiv.")
    elif role.get("role") not in {"EL", "FueAss"}:
        if not (
            role.get("role") == "AL"
            and record.get("abschnitt_id") == role.get("section_id")
        ) and not (
            role.get("role") == "Dokumentar" and record.get("created_by") == user["id"]
        ):
            raise HTTPException(403, "Korrektur nicht erlaubt.")
    allowed = (
        {"text", "absender", "empfaenger", "prioritaet", "funk_typ"}
        if kind == "messages"
        else {
            "name",
            "vorname",
            "nachname",
            "geburtsdatum",
            "sichtung",
            "notiz",
            "auffindeort",
            "bemerkung",
            "diagnose",
            "massnahmen",
        }
    )
    if kind == "incidents":
        allowed = {"name", "ort", "beschreibung"}
    if not archived and kind == "messages" and role.get("role") in {"EL", "FueAss"}:
        allowed.add("abschnitt_id")
    if not payload.changes or set(payload.changes) - allowed:
        raise HTTPException(422, "Nur dokumentarische Felder zulässig.")
    if (
        "abschnitt_id" in payload.changes
        and payload.changes["abschnitt_id"] is not None
    ):
        if not await db.abschnitte.find_one(
            {"id": payload.changes["abschnitt_id"], "incident_id": incident_id}
        ):
            raise HTTPException(422, "Ungültiger Abschnitt.")
    if "sichtung" in payload.changes and payload.changes["sichtung"] not in {
        "S0",
        "S1",
        "S2",
        "S3",
        None,
    }:
        raise HTTPException(422, "Ungültige Sichtung.")
    before = (
        {key: value for key, value in record.items() if key != "versions"}
        if kind != "incidents"
        else {key: record.get(key) for key in allowed}
    )
    changes = dict(payload.changes)
    if kind == "messages" and "abschnitt_id" in changes:
        changes["category"] = "section" if changes["abschnitt_id"] else "central"
    event = change_event(
        user,
        inc,
        "archive.correct" if archived else "message.correct",
        payload.reason,
        before,
        {**before, **changes},
    )
    version = record.get("revision", 0)
    query = (
        {**selector, "revision": version}
        if version
        else {**selector, "revision": {"$exists": False}}
    )
    result = await db[kind].update_one(
        query,
        {
            "$set": {**changes, "corrected": True},
            "$inc": {"revision": 1},
            "$push": {"versions": event},
        },
    )
    if not result.modified_count:
        raise HTTPException(409, "Eintrag wurde gleichzeitig geändert.")
    return {"corrected": True, "revision": version + 1}
