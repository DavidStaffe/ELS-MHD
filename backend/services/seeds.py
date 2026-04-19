"""Resource seeds, status helpers, bed-release helper, patient kennung counter."""
from datetime import datetime
import uuid

from fastapi import HTTPException

from core.db import db
from core.time import iso, now_utc


DEFAULT_RESOURCES = [
    {"name": "UHS Team 1", "typ": "intern", "kategorie": "uhs"},
    {"name": "UHS Team 2", "typ": "intern", "kategorie": "uhs"},
    {"name": "UHS Team 3", "typ": "intern", "kategorie": "uhs"},
    {"name": "Radstreife 1", "typ": "intern", "kategorie": "bike"},
    {"name": "RTW 1", "typ": "extern", "kategorie": "rtw"},
    {"name": "RTW 2", "typ": "extern", "kategorie": "rtw"},
    {"name": "KTW 1", "typ": "extern", "kategorie": "ktw"},
    {"name": "KTW 2", "typ": "extern", "kategorie": "ktw"},
    {"name": "NEF 1", "typ": "extern", "kategorie": "nef"},
]

DEFAULT_ZIEL_BY_TYP = {"intern": "uhs", "extern": "krankenhaus"}


async def seed_default_resources(incident_id: str):
    existing = await db.resources.count_documents({"incident_id": incident_id})
    if existing > 0:
        return
    now = now_utc()
    docs = []
    for defn in DEFAULT_RESOURCES:
        docs.append({
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "name": defn["name"],
            "typ": defn["typ"],
            "kategorie": defn["kategorie"],
            "status": "verfuegbar",
            "notiz": "",
            "abschnitt_id": None,
            "created_at": iso(now),
            "updated_at": iso(now),
        })
    if docs:
        await db.resources.insert_many(docs)


async def update_resource_status_by_name(incident_id: str, name: str, status: str):
    await db.resources.update_one(
        {"incident_id": incident_id, "name": name},
        {"$set": {"status": status, "updated_at": iso(now_utc())}},
    )


async def release_bett_for_patient(patient_id: str):
    """Zentral: Bett freigeben wenn Patient entlassen/uebergeben/Transport abgeschlossen."""
    b = await db.betten.find_one(
        {"patient_id": patient_id, "status": "belegt"}, {"_id": 0}
    )
    if not b:
        return
    await db.betten.update_one(
        {"id": b["id"]},
        {"$set": {"status": "frei", "patient_id": None, "belegt_seit": None}},
    )
    await db.patients.update_one(
        {"id": patient_id},
        {"$set": {"bett_id": None, "updated_at": iso(now_utc())}},
    )


async def next_kennung(incident_id: str) -> str:
    res = await db.incidents.find_one_and_update(
        {"id": incident_id},
        {"$inc": {"patient_counter": 1}},
        projection={"_id": 0, "patient_counter": 1},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    n = int(res.get("patient_counter") or 1)
    return f"P-{n:04d}"


async def ensure_transport_for_patient(patient: dict):
    """Legt offenen Transport an, falls noch keiner existiert."""
    from models import Transport
    if not patient.get("transport_typ"):
        return None
    existing = await db.transports.find_one(
        {"patient_id": patient["id"]}, {"_id": 0}
    )
    if existing:
        return existing
    typ = patient["transport_typ"]
    ziel = "rd" if typ == "extern" else "uhs"
    transport = Transport(
        incident_id=patient["incident_id"],
        patient_id=patient["id"],
        patient_kennung=patient.get("kennung"),
        patient_sichtung=patient.get("sichtung"),
        typ=typ,
        ziel=ziel,
        status="offen",
    )
    doc = transport.model_dump()
    for k in ("created_at", "updated_at", "zugewiesen_at", "gestartet_at", "abgeschlossen_at"):
        if isinstance(doc.get(k), datetime):
            doc[k] = iso(doc[k])
    await db.transports.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}
