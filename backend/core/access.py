"""Default-deny gate on every registered application route, including direct links."""

from fastapi import HTTPException, Request
from core.identity import (
    db,
    identity,
    require,
    incident_access,
    role_for,
    medical,
    audit,
)
from pymongo.errors import DuplicateKeyError

READS = frozenset(
    {
        "get_incident",
        "list_patients",
        "get_patient",
        "stream_patients",
        "list_resources",
        "list_transports",
        "get_transport",
        "list_messages",
        "get_message",
        "list_abschnitte",
        "get_abschnitt",
        "list_betten",
        "get_bett",
        "konflikte_endpoint",
        "auswertung_endpoint",
        "abschluss_check_endpoint",
        "report_endpoint",
        "list_report_versions",
        "divera_status",
        "list_fms_events",
        "resource_suggestions",
    }
)
WRITES = frozenset(
    {
        "update_incident",
        "patch_incident_meta",
        "create_patient",
        "create_dummy_patient",
        "update_patient",
        "reopen_patient",
        "complete_patient",
        "move_to_waiting_area",
        "confirm_sichtung",
        "create_transport",
        "update_transport",
        "create_resource",
        "update_resource",
        "create_abschnitt",
        "update_abschnitt",
        "create_bett",
        "create_betten_bulk",
        "update_bett",
        "assign_bett",
        "release_bett",
        "create_message",
        "ack_message",
        "confirm_message",
        "finalize_message",
        "create_report_version",
        "divera_start",
        "divera_stop",
        "divera_sync_now",
        "assign_resource",
        "release_resource",
        "acknowledge_fms",
    }
)
MEDICAL_MODULES = {
    "patients",
    "patient_disposition",
    "transports",
    "betten",
    "analytics",
}


async def _authorize(request: Request):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        from urllib.parse import urlparse
        import os

        origin = request.headers.get("origin")
        allowed = {
            o.strip()
            for o in os.environ.get("CORS_ORIGINS", "").split(",")
            if o.strip() != "*"
        }
        if (
            origin
            and origin not in allowed
            and not (
                urlparse(origin).scheme == "https"
                and urlparse(origin).netloc == request.url.netloc
            )
        ):
            raise HTTPException(403, "Anfrageherkunft nicht erlaubt.")
    endpoint = request.scope.get("endpoint")
    name = getattr(endpoint, "__name__", "")
    module = getattr(endpoint, "__module__", "").split(".")[-1]
    if module == "identity":
        if name not in {"login", "setup", "recover"}:
            unrestricted = {"me", "logout", "lock", "unlock", "anonymous_events"}
            await identity(
                request,
                allow_locked=name in unrestricted,
                allow_change=name in unrestricted | {"password"},
            )
        return  # Narrower account policy is also checked inside the route.
    if module == "governance":
        await identity(request)
        return  # Authenticate before taking any mutation lock; route checks scope.
    if module == "incidents" and name in {"root", "meta"}:
        return
    user = await identity(request)
    if module == "admin":
        # The shared legacy password no longer creates an alternate identity.
        raise HTTPException(410, "Bitte persönliche Anmeldung verwenden.")
    if module == "divera" and name == "divera_configured":
        return
    if module == "system_updates" or (
        module == "divera" and not request.path_params.get("incident_id")
    ):
        require(user, "settings.manage")
        return
    if module == "keywords":
        if request.method != "GET":
            require(user, "settings.manage")
        return
    if name in {"list_incidents", "stream_incidents"}:
        return  # List endpoint redacts; stream sends anonymous invalidations only.
    if name in {"create_incident", "create_demo_incident"}:
        require(user, "incidents.create")
        return
    params = request.path_params
    incident_id = params.get("incident_id")
    record = None
    for key, collection in {
        "patient_id": "patients",
        "resource_id": "resources",
        "transport_id": "transports",
        "message_id": "messages",
        "abschnitt_id": "abschnitte",
        "bett_id": "betten",
        "event_id": "fms_events",
    }.items():
        if key in params:
            record = await db[collection].find_one({"id": params[key]}, {"_id": 0})
            if not record:
                raise HTTPException(404, "Objekt nicht gefunden.")
            incident_id = record.get("incident_id")
            break
    incident = (
        await db.incidents.find_one({"id": incident_id}, {"_id": 0})
        if incident_id
        else None
    )
    if not incident or not await incident_access(user, incident):
        raise HTTPException(403, "Kein Zugriff auf diesen Einsatz.")
    request.state.incident = incident
    request.state.record = record
    assignment = role_for(user, incident)
    role = assignment.get("role")
    if (
        module in MEDICAL_MODULES
        and not medical(user, incident)
        and not (
            role == "Helfer"
            and name
            in {"list_patients", "get_patient", "update_patient", "create_patient"}
        )
    ):
        raise HTTPException(403, "Medizinische Leseberechtigung fehlt.")
    if request.method == "GET" and name in READS:
        if role == "Helfer" and incident.get("created_by") != user["id"]:
            # Collection and aggregate endpoints cannot be safely exposed to helpers.
            if name not in {"get_patient", "list_patients", "list_resources"}:
                raise HTTPException(403, "Nur eigene Patienten verfügbar.")
            query = {"id": assignment.get("resource_id"), "incident_id": incident_id}
            if name == "get_patient":
                query["bound_patient_id"] = params.get("patient_id")
            resource = await db.resources.find_one(query)
            if not resource:
                raise HTTPException(403, "Aktuelle Ressourcenbindung fehlt.")
        return
    if (
        request.method == "GET"
        and name == "incident_divera_vehicles"
        and role in {"EL", "FueAss"}
    ):
        return
    if name not in WRITES or request.method == "DELETE":
        raise HTTPException(403, "Aktion nicht freigegeben.")
    if incident.get("status") == "abgeschlossen":
        raise HTTPException(409, "Archiv ist schreibgeschützt.")
    raw_body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    body = raw_body if isinstance(raw_body, dict) else {}
    for field, collection in {
        "patient_id": "patients",
        "resource_id": "resources",
        "behandlung_ressource_id": "resources",
        "zugewiesene_ressource_id": "resources",
        "abschnitt_id": "abschnitte",
        "bett_id": "betten",
        "keyword_id": "keywords",
    }.items():
        if body.get(field):
            query = {"id": body[field]}
            if collection != "keywords":
                query["incident_id"] = incident_id
            referenced = await db[collection].find_one(query)
            if not referenced:
                raise HTTPException(422, "Referenz gehört nicht zum Einsatz.")
            if field == "behandlung_ressource_id" and referenced.get("kategorie") != "uhs":
                if not params.get("patient_id") or referenced.get("bound_patient_id") != params["patient_id"]:
                    raise HTTPException(409, "Normale Ressource zuerst ausdrücklich zum Patienten disponieren.")
            if (
                role == "AL"
                and collection in {"patients", "resources", "betten"}
                and referenced.get("abschnitt_id") != assignment.get("section_id")
            ):
                raise HTTPException(403, "Referenz außerhalb des eigenen Abschnitts.")
    if "zugewiesene_ressource_id" in body and name != "assign_resource":
        raise HTTPException(
            403, "Patientendisposition nur über den Dispositionsablauf."
        )
    if name == "update_incident" and any(k in body for k in ("status", "end_at")):
        raise HTTPException(
            409, "Statuswechsel nur über begründeten Abschluss/Wiedereröffnung."
        )
    if name == "release_resource" and role != "EL":
        raise HTTPException(403, "Nur die aktive EL darf Ressourcen freigeben.")
    if name == "update_resource" and any(
        k in body for k in ("bound_patient_id", "zugewiesene_ressource_id")
    ):
        raise HTTPException(403, "Ressourcenbindung nur über Disposition ändern.")
    if (
        name == "update_resource"
        and body.get("status") == "verfuegbar"
        and role != "EL"
    ):
        raise HTTPException(403, "Nur EL darf Ressourcen freigeben.")
    if role in {"EL", "FueAss"}:
        pass
    elif role == "AL":
        section = assignment.get("section_id")
        target_section = (
            record.get("id")
            if module == "abschnitte" and record
            else (record or body).get("abschnitt_id")
        )
        if module == "transports":
            patient = await db.patients.find_one({"id": (record or body).get("patient_id"), "incident_id": incident_id})
            target_section = patient.get("abschnitt_id") if patient else None
        if name == "release_resource" or not section or target_section != section:
            raise HTTPException(403, "Schreibzugriff nur im eigenen Abschnitt.")
        if "abschnitt_id" in body and body["abschnitt_id"] != section:
            raise HTTPException(403, "Abschnittswechsel nicht erlaubt.")
    elif role == "Dokumentar" and name == "create_message":
        pass
    elif role == "Helfer" and name in {"update_patient", "create_patient"}:
        require(
            user,
            (
                "helpers.patients.update"
                if name == "update_patient"
                else "helpers.patients.create"
            ),
        )
        resource = await db.resources.find_one(
            {"id": assignment.get("resource_id"), "incident_id": incident_id}
        )
        if not resource or (
            name == "update_patient"
            and resource.get("bound_patient_id") != params.get("patient_id")
        ):
            raise HTTPException(403, "Aktuelle Ressourcenbindung fehlt.")
        allowed = {
            "sichtung",
            "notiz",
            "abschnitt_id",
            "auffindeort",
            "auffinde_lat",
            "auffinde_lng",
            "keyword_id",
        }
        if set(body) - allowed:
            raise HTTPException(
                403,
                "Helfer dürfen nur ausdrücklich freigegebene Patientendaten bearbeiten.",
            )
        if "abschnitt_id" in body and body["abschnitt_id"] != resource.get(
            "abschnitt_id"
        ):
            raise HTTPException(403, "Nur der eigene Ressourcenabschnitt.")
    else:
        raise HTTPException(403, "Keine operative Berechtigung.")


async def authorize(request: Request):
    """Serialize incident mutations, then recheck access under the lock.

    No expiring lease: an interrupted process leaves this incident fail-closed
    until the operator has checked the interrupted write and cleared its lock.
    """
    try:
        await _authorize(request)
    except HTTPException as exc:
        actor = getattr(request.state, "user", None)
        if actor:
            await audit(
                actor,
                "access.denied",
                data={
                    "path": request.url.path,
                    "method": request.method,
                    "status": exc.status_code,
                },
            )
        raise
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        yield
        return
    incident_id = request.path_params.get("incident_id") or getattr(
        request.state, "incident", {}
    ).get("id")
    target_user = request.path_params.get("user_id")
    if request.url.path.endswith("/assignments"):
        target_user = (await request.json()).get("user_id")
    lock_ids = (["user:" + target_user] if target_user else []) + (
        ["incident:" + incident_id] if incident_id else []
    )
    acquired = []
    try:
        for lock_id in lock_ids:
            try:
                await db.identity_locks.insert_one({"_id": lock_id})
                acquired.append(lock_id)
            except DuplicateKeyError:
                raise HTTPException(
                    409, "Objekt wird gerade geändert. Bitte erneut versuchen."
                ) from None
        if lock_ids:
            await _authorize(request)
        user = getattr(request.state, "user", None)
        if user:
            await audit(
                user,
                "request.started",
                incident_id=incident_id,
                data={"path": request.url.path, "method": request.method},
            )
        try:
            yield
        except Exception:
            if user:
                await audit(
                    user,
                    "request.failed",
                    incident_id=incident_id,
                    data={"path": request.url.path},
                )
            raise
        else:
            if user:
                await audit(
                    user,
                    "request.completed",
                    incident_id=incident_id,
                    data={"path": request.url.path},
                )
    finally:
        for lock_id in reversed(acquired):
            await db.identity_locks.delete_one({"_id": lock_id})
