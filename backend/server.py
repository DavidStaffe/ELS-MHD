from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_iso(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def serialize_incident(doc: dict) -> dict:
    """MongoDB-Dokument -> API-ready dict."""
    doc = {k: v for k, v in doc.items() if k != "_id"}
    for k in ("start_at", "end_at", "created_at", "updated_at"):
        if k in doc and isinstance(doc[k], datetime):
            doc[k] = iso(doc[k])
    return doc


# ---------------------------------------------------------------------------
# Incident Models
# ---------------------------------------------------------------------------

IncidentTyp = Literal[
    "veranstaltung",
    "sanitaetsdienst",
    "uebung",
    "einsatz",
    "sonstiges",
]

IncidentStatus = Literal[
    "geplant",
    "operativ",
    "abgeschlossen",
    "archiviert",
]

SichtungStufe = Literal["S0", "S1", "S2", "S3"]
PatientStatus = Literal[
    "wartend",
    "in_behandlung",
    "transportbereit",
    "uebergeben",
    "entlassen",
]
PatientVerbleib = Literal[
    "unbekannt",
    "uhs",
    "rd",
    "krankenhaus",
    "event",
    "heim",
    "sonstiges",
]

TransportTyp = Literal["intern", "extern"]
FallabschlussTyp = Literal["rd_uebergabe", "entlassung", "manuell"]

TransportZiel = Literal[
    "uhs",
    "krankenhaus",
    "rd",
    "event",
    "heim",
    "sonstiges",
]
TransportStatus = Literal[
    "offen",
    "zugewiesen",
    "unterwegs",
    "abgeschlossen",
]

ResourceKategorie = Literal["uhs", "rtw", "ktw", "nef", "bike", "sonstiges"]
ResourceStatus = Literal["verfuegbar", "im_einsatz", "wartung", "offline"]

MessagePrio = Literal["kritisch", "dringend", "normal"]
MessageKat = Literal["info", "lage", "anforderung", "warnung"]


class IncidentBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=2, max_length=120)
    typ: IncidentTyp = "veranstaltung"
    ort: str = Field(min_length=0, max_length=180, default="")
    beschreibung: str = Field(default="", max_length=2000)


class IncidentCreate(IncidentBase):
    start_at: Optional[datetime] = None
    status: IncidentStatus = "operativ"
    demo: bool = False


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    typ: Optional[IncidentTyp] = None
    ort: Optional[str] = None
    beschreibung: Optional[str] = None
    status: Optional[IncidentStatus] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class Incident(IncidentBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: IncidentStatus = "operativ"
    demo: bool = False
    start_at: datetime = Field(default_factory=now_utc)
    end_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


# ---------------------------------------------------------------------------
# Root / Meta
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root():
    return {"message": "ELS MHD API", "version": "0.2.0"}


@api_router.get("/meta")
async def meta():
    return {
        "app": "ELS MHD",
        "name": "Einsatzleitsystem Malteser Hilfsdienst",
        "version": "0.9.0",
        "step": "07–09 Rollen · Demo · Auswertung",
    }


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

@api_router.get("/incidents", response_model=List[dict])
async def list_incidents(status: Optional[IncidentStatus] = None, demo: Optional[bool] = None):
    query: dict = {}
    if status:
        query["status"] = status
    if demo is not None:
        query["demo"] = demo

    cursor = db.incidents.find(query, {"_id": 0}).sort("created_at", -1)
    rows = await cursor.to_list(500)

    for r in rows:
        for k in ("start_at", "end_at", "created_at", "updated_at"):
            if k in r and isinstance(r[k], str):
                # Felder in Strings belassen – Frontend parst
                pass
    return rows


@api_router.post("/incidents", response_model=dict, status_code=201)
async def create_incident(payload: IncidentCreate):
    obj = Incident(
        **payload.model_dump(exclude_none=True),
    )
    # Falls start_at nicht mitgegeben, setze auf jetzt
    if payload.start_at is None:
        obj.start_at = now_utc()

    doc = obj.model_dump()
    for k in ("start_at", "end_at", "created_at", "updated_at"):
        if isinstance(doc.get(k), datetime):
            doc[k] = iso(doc[k])

    await db.incidents.insert_one(doc)
    await _seed_default_resources(obj.id)
    return serialize_incident(doc)


@api_router.post("/incidents/demo", response_model=dict, status_code=201)
async def create_demo_incident():
    """
    Legt einen vollstaendigen Demo-Incident mit realistischen Vordaten an.
    Schritt 08 wird diesen Seed um Patienten/Transporte/Ressourcen erweitern.
    """
    orte = [
        "Festplatz Sued",
        "Stadtpark West",
        "Messehalle 3",
        "Marathon KM 21",
        "Stadion Ost-Kurve",
    ]
    typen = ["veranstaltung", "sanitaetsdienst", "uebung"]
    namen = [
        "Stadtfest 2026",
        "Marathon Muenchen",
        "Open-Air Festival",
        "MANV-Uebung Sued",
        "Grossveranstaltung Messe",
    ]

    start = now_utc() - timedelta(minutes=random.randint(5, 180))

    obj = Incident(
        name=random.choice(namen),
        typ=random.choice(typen),  # type: ignore
        ort=random.choice(orte),
        beschreibung="Automatisch erzeugter Demo-Incident. Vordaten fuer Training und Tests.",
        status="operativ",
        demo=True,
        start_at=start,
    )

    doc = obj.model_dump()
    for k in ("start_at", "end_at", "created_at", "updated_at"):
        if isinstance(doc.get(k), datetime):
            doc[k] = iso(doc[k])

    await db.incidents.insert_one(doc)
    await _seed_default_resources(obj.id)

    # --- Schritt 08: Realistische Vordaten (Patienten, Transporte, Meldungen) ---
    await _seed_demo_data(obj.id, start)

    logger.info("Demo-Incident erstellt: %s (%s)", obj.name, obj.id)
    return serialize_incident(doc)


async def _seed_demo_data(incident_id: str, incident_start: datetime):
    """Legt Patienten, Transporte und Meldungen fuer einen Demo-Incident an."""
    now = now_utc()

    notizen_by_sichtung = {
        "S1": [
            "Kollaps am Hauptzugang, reagiert nicht auf Ansprache",
            "Starke Blutung Oberschenkel nach Sturz",
        ],
        "S2": [
            "Kreislaufstoerung, hyperton",
            "Knieverletzung, gehfaehig mit Hilfe",
            "Hitzeerschoepfung, desorientiert",
        ],
        "S3": [
            "Schnittwunde Handflaeche, Wunde gesaeubert",
            "Insektenstich Ohrlaeppchen",
            "Leichter Kreislauf, Wasser erhalten",
        ],
        "S0": [
            "Pflasterwunsch Knie",
            "Hitzebeschwerden, Ruhe erhalten",
        ],
    }

    patients_plan = [
        ("S1", "in_behandlung", "unbekannt", 5),
        ("S1", "transportbereit", "rd", 18),
        ("S2", "in_behandlung", "unbekannt", 11),
        ("S2", "uebergeben", "rd", 42),
        ("S3", "entlassen", "event", 28),
        ("S0", "entlassen", "event", 7),
        ("S3", "in_behandlung", "unbekannt", 3),
    ]

    counter = 0
    for (sichtung, status, verbleib, ago_min) in patients_plan:
        counter += 1
        await db.incidents.update_one({"id": incident_id}, {"$inc": {"patient_counter": 1}})
        kennung = f"P-{counter:04d}"
        ankunft = now - timedelta(minutes=ago_min)
        sichtung_at = ankunft + timedelta(minutes=1)
        behandlung_start_at = sichtung_at
        transport_at = None
        fallabschluss_at = None
        if status in ("transportbereit", "uebergeben"):
            transport_at = sichtung_at + timedelta(minutes=4)
        if status in ("uebergeben", "entlassen"):
            fallabschluss_at = (transport_at or sichtung_at) + timedelta(minutes=6)

        notiz = random.choice(notizen_by_sichtung[sichtung])
        patient_doc = {
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "kennung": kennung,
            "sichtung": sichtung,
            "status": status,
            "verbleib": verbleib,
            "notiz": notiz,
            "transport_typ": "extern" if status in ("transportbereit", "uebergeben") else None,
            "fallabschluss_typ": "rd_uebergabe" if status == "uebergeben" else ("entlassung" if status == "entlassen" else None),
            "created_at": iso(ankunft),
            "updated_at": iso(now),
            "sichtung_at": iso(sichtung_at),
            "behandlung_start_at": iso(behandlung_start_at),
            "transport_angefordert_at": iso(transport_at) if transport_at else None,
            "fallabschluss_at": iso(fallabschluss_at) if fallabschluss_at else None,
        }
        await db.patients.insert_one(patient_doc)

        # Transport-Eintrag
        if patient_doc["transport_typ"]:
            t_status = (
                "abgeschlossen" if status == "uebergeben"
                else "unterwegs" if status == "transportbereit"
                else "offen"
            )
            ressource = "RTW 1" if t_status in ("unterwegs", "abgeschlossen") else None
            transport_doc = {
                "id": str(uuid.uuid4()),
                "incident_id": incident_id,
                "patient_id": patient_doc["id"],
                "patient_kennung": kennung,
                "patient_sichtung": sichtung,
                "typ": "extern",
                "ziel": "krankenhaus" if t_status != "offen" else "rd",
                "ressource": ressource,
                "notiz": "",
                "status": t_status,
                "created_at": iso(transport_at or sichtung_at),
                "updated_at": iso(now),
                "zugewiesen_at": iso(transport_at) if ressource else None,
                "gestartet_at": iso(transport_at + timedelta(minutes=1)) if t_status in ("unterwegs", "abgeschlossen") else None,
                "abgeschlossen_at": iso(fallabschluss_at) if t_status == "abgeschlossen" else None,
            }
            await db.transports.insert_one(transport_doc)
            if ressource and t_status != "abgeschlossen":
                await _update_resource_status_by_name(incident_id, ressource, "im_einsatz")

    # --- Meldungen ---
    messages = [
        ("kritisch", "anforderung", "SAN 1", "Kollaps Haupteingang, zweiten Trupp alarmieren!", now - timedelta(minutes=9)),
        ("dringend", "lage", "UHS", "UHS Kapazitaet 80% erreicht", now - timedelta(minutes=15)),
        ("normal", "info", "EL", "Einsatz laeuft planmaessig", now - timedelta(minutes=30)),
    ]
    for prio, kat, von, text, when in messages:
        await db.messages.insert_one({
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "text": text,
            "prioritaet": prio,
            "kategorie": kat,
            "von": von,
            "quittiert_at": iso(now - timedelta(minutes=2)) if prio == "normal" else None,
            "quittiert_von": "Einsatzleiter" if prio == "normal" else None,
            "created_at": iso(when),
        })

    # --- Schritt 10: Einsatzabschnitte ---
    abschnitt_nord = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "name": "Abschnitt Nord",
        "farbe": "red",
        "beschreibung": "Hauptbuehne / Eingang Nord",
        "aktiv": True,
        "erstellt_um": iso(incident_start),
    }
    abschnitt_bhp = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "name": "BHP / UHS",
        "farbe": "blue",
        "beschreibung": "Behandlungsplatz, Zelt Sued",
        "aktiv": True,
        "erstellt_um": iso(incident_start),
    }
    await db.abschnitte.insert_many([abschnitt_nord, abschnitt_bhp])

    # Ordne Demo-Ressourcen den Abschnitten zu
    uhs_resources = await db.resources.find(
        {"incident_id": incident_id, "kategorie": "uhs"}, {"_id": 0}
    ).to_list(20)
    for r in uhs_resources[:2]:
        await db.resources.update_one(
            {"id": r["id"]}, {"$set": {"abschnitt_id": abschnitt_bhp["id"]}}
        )
    for r in uhs_resources[2:]:
        await db.resources.update_one(
            {"id": r["id"]}, {"$set": {"abschnitt_id": abschnitt_nord["id"]}}
        )
    rtw_resources = await db.resources.find(
        {"incident_id": incident_id, "kategorie": {"$in": ["rtw", "ktw"]}}, {"_id": 0}
    ).to_list(20)
    for r in rtw_resources[:2]:
        await db.resources.update_one(
            {"id": r["id"]}, {"$set": {"abschnitt_id": abschnitt_bhp["id"]}}
        )

    # --- Schritt 11: Behandlungsbetten (6 Betten: 4 belegt, 2 frei) ---
    betten_plan = [
        {"name": "Bett 1", "typ": "liegend", "abschnitt": abschnitt_bhp["id"]},
        {"name": "Bett 2", "typ": "liegend", "abschnitt": abschnitt_bhp["id"]},
        {"name": "Bett 3", "typ": "sitzend", "abschnitt": abschnitt_bhp["id"]},
        {"name": "Bett 4", "typ": "sitzend", "abschnitt": abschnitt_bhp["id"]},
        {"name": "Schockraum 1", "typ": "schockraum", "abschnitt": abschnitt_bhp["id"]},
        {"name": "Beobachtung A", "typ": "beobachtung", "abschnitt": abschnitt_nord["id"]},
    ]
    bett_ids = []
    for i, bp in enumerate(betten_plan):
        bdoc = {
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "name": bp["name"],
            "typ": bp["typ"],
            "status": "frei",
            "abschnitt_id": bp["abschnitt"],
            "notiz": "",
            "patient_id": None,
            "belegt_seit": None,
            "erstellt_um": iso(incident_start + timedelta(minutes=i)),
        }
        await db.betten.insert_one(bdoc)
        bett_ids.append(bdoc["id"])

    # 4 der 6 Betten mit aktiven Patienten belegen (in_behandlung + transportbereit)
    active_patients = await db.patients.find(
        {"incident_id": incident_id, "status": {"$in": ["in_behandlung", "transportbereit"]}},
        {"_id": 0},
    ).to_list(20)
    for i, p in enumerate(active_patients[:4]):
        bid = bett_ids[i]
        belegt = now - timedelta(minutes=random.randint(5, 25))
        await db.betten.update_one(
            {"id": bid},
            {"$set": {
                "status": "belegt",
                "patient_id": p["id"],
                "belegt_seit": iso(belegt),
            }},
        )
        await db.patients.update_one(
            {"id": p["id"]},
            {"$set": {"bett_id": bid, "updated_at": iso(now)}},
        )


@api_router.get("/incidents/{incident_id}", response_model=dict)
async def get_incident(incident_id: str):
    doc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    return doc


@api_router.patch("/incidents/{incident_id}", response_model=dict)
async def update_incident(incident_id: str, payload: IncidentUpdate):
    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Keine Aenderungen angegeben")

    for k in ("start_at", "end_at"):
        if k in update and isinstance(update[k], datetime):
            update[k] = iso(update[k])

    update["updated_at"] = iso(now_utc())

    # Automatisch end_at setzen beim Abschluss
    if update.get("status") == "abgeschlossen":
        existing = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
        if existing and not existing.get("end_at"):
            update["end_at"] = iso(now_utc())

    result = await db.incidents.find_one_and_update(
        {"id": incident_id},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    return result


@api_router.delete("/incidents/{incident_id}", status_code=204)
async def delete_incident(incident_id: str):
    result = await db.incidents.delete_one({"id": incident_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    await db.patients.delete_many({"incident_id": incident_id})
    await db.transports.delete_many({"incident_id": incident_id})
    await db.resources.delete_many({"incident_id": incident_id})
    await db.messages.delete_many({"incident_id": incident_id})
    await db.abschnitte.delete_many({"incident_id": incident_id})
    await db.betten.delete_many({"incident_id": incident_id})
    return None


# ---------------------------------------------------------------------------
# Patienten
# ---------------------------------------------------------------------------


class PatientBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sichtung: Optional[SichtungStufe] = None
    status: PatientStatus = "wartend"
    verbleib: PatientVerbleib = "unbekannt"
    notiz: str = Field(default="", max_length=4000)
    transport_typ: Optional[TransportTyp] = None
    fallabschluss_typ: Optional[FallabschlussTyp] = None
    bett_id: Optional[str] = None


class PatientCreate(PatientBase):
    # optional fuer manuelle Erfassung
    sichtung: Optional[SichtungStufe] = None


class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sichtung: Optional[SichtungStufe] = None
    status: Optional[PatientStatus] = None
    verbleib: Optional[PatientVerbleib] = None
    notiz: Optional[str] = None
    transport_typ: Optional[TransportTyp] = None
    fallabschluss_typ: Optional[FallabschlussTyp] = None
    bett_id: Optional[str] = None


class Patient(PatientBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    kennung: str
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    sichtung_at: Optional[datetime] = None
    behandlung_start_at: Optional[datetime] = None
    transport_angefordert_at: Optional[datetime] = None
    fallabschluss_at: Optional[datetime] = None
    transport_typ: Optional[TransportTyp] = None
    fallabschluss_typ: Optional[FallabschlussTyp] = None


def _serialize_patient(doc: dict) -> dict:
    doc = {k: v for k, v in doc.items() if k != "_id"}
    for k in (
        "created_at",
        "updated_at",
        "sichtung_at",
        "behandlung_start_at",
        "transport_angefordert_at",
        "fallabschluss_at",
    ):
        if k in doc and isinstance(doc[k], datetime):
            doc[k] = iso(doc[k])
    return doc


async def _next_kennung(incident_id: str) -> str:
    """
    Atomar inkrementierender Zaehler pro Incident.
    Liefert P-0001, P-0002, ... zurueck.
    """
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


@api_router.get("/incidents/{incident_id}/patients", response_model=List[dict])
async def list_patients(
    incident_id: str,
    sichtung: Optional[str] = None,  # comma separated "S1,S2"
    status: Optional[str] = None,
    verbleib: Optional[str] = None,
):
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    query: dict = {"incident_id": incident_id}
    if sichtung:
        vals = [v.strip() for v in sichtung.split(",") if v.strip()]
        if vals:
            query["sichtung"] = {"$in": vals}
    if status:
        vals = [v.strip() for v in status.split(",") if v.strip()]
        if vals:
            query["status"] = {"$in": vals}
    if verbleib:
        vals = [v.strip() for v in verbleib.split(",") if v.strip()]
        if vals:
            query["verbleib"] = {"$in": vals}

    cursor = db.patients.find(query, {"_id": 0}).sort("created_at", 1)
    rows = await cursor.to_list(2000)
    return rows


@api_router.post("/incidents/{incident_id}/patients", response_model=dict, status_code=201)
async def create_patient(incident_id: str, payload: PatientCreate):
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    kennung = await _next_kennung(incident_id)
    now = now_utc()

    patient = Patient(
        **payload.model_dump(exclude_none=True),
        incident_id=incident_id,
        kennung=kennung,
    )
    # Zeitstempel-Logik: Sichtung gesetzt => sichtung_at + behandlung_start_at
    if patient.sichtung:
        patient.sichtung_at = now
        patient.behandlung_start_at = now
        # Status automatisch auf in_behandlung wenn gerade mit Sichtung erfasst
        if payload.status == "wartend":
            patient.status = "in_behandlung"

    doc = patient.model_dump()
    for k in (
        "created_at",
        "updated_at",
        "sichtung_at",
        "behandlung_start_at",
        "transport_angefordert_at",
        "fallabschluss_at",
    ):
        if isinstance(doc.get(k), datetime):
            doc[k] = iso(doc[k])

    await db.patients.insert_one(doc)
    return _serialize_patient(doc)


@api_router.get("/patients/{patient_id}", response_model=dict)
async def get_patient(patient_id: str):
    doc = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    return doc


@api_router.patch("/patients/{patient_id}", response_model=dict)
async def update_patient(patient_id: str, payload: PatientUpdate):
    existing = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")

    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Keine Aenderungen angegeben")

    now = now_utc()
    update["updated_at"] = iso(now)

    # Sichtung neu gesetzt -> Behandlungsstart
    if "sichtung" in update and not existing.get("sichtung_at"):
        update["sichtung_at"] = iso(now)
        if not existing.get("behandlung_start_at"):
            update["behandlung_start_at"] = iso(now)

    # Transport-Typ gesetzt -> automatisch status=transportbereit + Zeitstempel
    if "transport_typ" in update and update["transport_typ"]:
        if existing.get("status") not in ("transportbereit", "uebergeben", "entlassen"):
            update.setdefault("status", "transportbereit")
        if not existing.get("transport_angefordert_at"):
            update["transport_angefordert_at"] = iso(now)

    # Fallabschluss-Typ gesetzt -> status entsprechend + Zeitstempel + Default-Verbleib
    if "fallabschluss_typ" in update and update["fallabschluss_typ"]:
        typ = update["fallabschluss_typ"]
        if typ == "rd_uebergabe":
            update.setdefault("status", "uebergeben")
            if not existing.get("verbleib") or existing.get("verbleib") == "unbekannt":
                update.setdefault("verbleib", "rd")
        elif typ == "entlassung":
            update.setdefault("status", "entlassen")
            if not existing.get("verbleib") or existing.get("verbleib") == "unbekannt":
                update.setdefault("verbleib", "event")
        elif typ == "manuell":
            update.setdefault("status", "entlassen")
        if not existing.get("fallabschluss_at"):
            update["fallabschluss_at"] = iso(now)

    new_status = update.get("status")
    if new_status == "transportbereit" and not existing.get("transport_angefordert_at"):
        update["transport_angefordert_at"] = iso(now)
    if new_status in ("entlassen", "uebergeben") and not existing.get("fallabschluss_at"):
        update["fallabschluss_at"] = iso(now)

    result = await db.patients.find_one_and_update(
        {"id": patient_id},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )
    # Auto-Create Transport falls transport_typ frisch gesetzt wurde
    if "transport_typ" in update and update["transport_typ"]:
        await _ensure_transport_for_patient(result)
    # Bei Fallabschluss: zugehoerigen Transport auf abgeschlossen setzen
    if update.get("status") in ("uebergeben", "entlassen"):
        await db.transports.update_many(
            {"patient_id": patient_id, "status": {"$ne": "abgeschlossen"}},
            {
                "$set": {
                    "status": "abgeschlossen",
                    "abgeschlossen_at": iso(now),
                    "updated_at": iso(now),
                }
            },
        )
        # Bett automatisch freigeben
        await _release_bett_for_patient(patient_id)
    return result


@api_router.delete("/patients/{patient_id}", status_code=204)
async def delete_patient(patient_id: str):
    result = await db.patients.delete_one({"id": patient_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    # Zugehoerige Transporte mit entfernen
    await db.transports.delete_many({"patient_id": patient_id})
    return None


# ---------------------------------------------------------------------------
# Transporte
# ---------------------------------------------------------------------------


class TransportBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    typ: TransportTyp
    ziel: TransportZiel = "sonstiges"
    ressource: Optional[str] = None
    notiz: str = Field(default="", max_length=2000)


class TransportCreate(TransportBase):
    patient_id: Optional[str] = None


class TransportUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    typ: Optional[TransportTyp] = None
    ziel: Optional[TransportZiel] = None
    ressource: Optional[str] = None
    status: Optional[TransportStatus] = None
    notiz: Optional[str] = None


class Transport(TransportBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    patient_id: Optional[str] = None
    patient_kennung: Optional[str] = None
    patient_sichtung: Optional[SichtungStufe] = None
    status: TransportStatus = "offen"
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    zugewiesen_at: Optional[datetime] = None
    gestartet_at: Optional[datetime] = None
    abgeschlossen_at: Optional[datetime] = None


def _serialize_transport(doc: dict) -> dict:
    doc = {k: v for k, v in doc.items() if k != "_id"}
    for k in (
        "created_at",
        "updated_at",
        "zugewiesen_at",
        "gestartet_at",
        "abgeschlossen_at",
    ):
        if k in doc and isinstance(doc[k], datetime):
            doc[k] = iso(doc[k])
    return doc


DEFAULT_ZIEL_BY_TYP = {"intern": "uhs", "extern": "krankenhaus"}


async def _ensure_transport_for_patient(patient: dict):
    """
    Legt einen offenen Transport an, falls noch keiner fuer den Patienten existiert.
    Wird beim Setzen von patient.transport_typ aufgerufen.
    """
    if not patient.get("transport_typ"):
        return None
    existing = await db.transports.find_one(
        {"patient_id": patient["id"]},
        {"_id": 0},
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
    return _serialize_transport(doc)


@api_router.get("/incidents/{incident_id}/transports", response_model=List[dict])
async def list_transports(
    incident_id: str,
    typ: Optional[str] = None,
    status: Optional[str] = None,
):
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    query: dict = {"incident_id": incident_id}
    if typ:
        vals = [v.strip() for v in typ.split(",") if v.strip()]
        if vals:
            query["typ"] = {"$in": vals}
    if status:
        vals = [v.strip() for v in status.split(",") if v.strip()]
        if vals:
            query["status"] = {"$in": vals}

    cursor = db.transports.find(query, {"_id": 0}).sort("created_at", 1)
    rows = await cursor.to_list(2000)
    return rows


@api_router.post("/incidents/{incident_id}/transports", response_model=dict, status_code=201)
async def create_transport(incident_id: str, payload: TransportCreate):
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    patient_kennung = None
    patient_sichtung = None
    if payload.patient_id:
        p = await db.patients.find_one({"id": payload.patient_id}, {"_id": 0})
        if not p:
            raise HTTPException(status_code=404, detail="Patient nicht gefunden")
        if p.get("incident_id") != incident_id:
            raise HTTPException(status_code=400, detail="Patient gehoert nicht zu diesem Incident")
        patient_kennung = p.get("kennung")
        patient_sichtung = p.get("sichtung")

    transport = Transport(
        incident_id=incident_id,
        patient_id=payload.patient_id,
        patient_kennung=patient_kennung,
        patient_sichtung=patient_sichtung,
        typ=payload.typ,
        ziel=payload.ziel or DEFAULT_ZIEL_BY_TYP.get(payload.typ, "sonstiges"),
        ressource=payload.ressource,
        notiz=payload.notiz,
        status="zugewiesen" if payload.ressource else "offen",
    )
    if payload.ressource:
        transport.zugewiesen_at = now_utc()

    doc = transport.model_dump()
    for k in ("created_at", "updated_at", "zugewiesen_at", "gestartet_at", "abgeschlossen_at"):
        if isinstance(doc.get(k), datetime):
            doc[k] = iso(doc[k])

    await db.transports.insert_one(doc)
    if payload.ressource:
        await _update_resource_status_by_name(incident_id, payload.ressource, "im_einsatz")
    return _serialize_transport(doc)


@api_router.get("/transports/{transport_id}", response_model=dict)
async def get_transport(transport_id: str):
    doc = await db.transports.find_one({"id": transport_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Transport nicht gefunden")
    return doc


@api_router.patch("/transports/{transport_id}", response_model=dict)
async def update_transport(transport_id: str, payload: TransportUpdate):
    existing = await db.transports.find_one({"id": transport_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Transport nicht gefunden")

    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Keine Aenderungen angegeben")

    now = now_utc()
    update["updated_at"] = iso(now)

    # Ressource gesetzt -> wenn noch offen, auf zugewiesen + Zeitstempel
    if "ressource" in update and update["ressource"]:
        if existing.get("status") in (None, "offen"):
            update.setdefault("status", "zugewiesen")
        if not existing.get("zugewiesen_at"):
            update["zugewiesen_at"] = iso(now)
    elif "ressource" in update and update["ressource"] in (None, ""):
        # Ressource entfernt -> zurueck auf offen
        if existing.get("status") == "zugewiesen":
            update.setdefault("status", "offen")

    new_status = update.get("status")
    if new_status == "unterwegs" and not existing.get("gestartet_at"):
        update["gestartet_at"] = iso(now)
    if new_status == "abgeschlossen" and not existing.get("abgeschlossen_at"):
        update["abgeschlossen_at"] = iso(now)
    if new_status == "zugewiesen" and not existing.get("zugewiesen_at"):
        update["zugewiesen_at"] = iso(now)

    result = await db.transports.find_one_and_update(
        {"id": transport_id},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )

    # Ressourcen-Status synchronisieren
    existing_ressource = existing.get("ressource")
    new_ressource = result.get("ressource")
    new_status = result.get("status")

    # Alte Ressource: wenn Transport abgeschlossen oder Ressource-Wechsel -> freigeben (wenn nicht anderweitig belegt)
    async def _release_if_free(ressource_name: str):
        if not ressource_name:
            return
        # Pruefe ob andere aktive Transporte diese Ressource nutzen
        other = await db.transports.find_one(
            {
                "incident_id": result["incident_id"],
                "ressource": ressource_name,
                "id": {"$ne": transport_id},
                "status": {"$in": ["zugewiesen", "unterwegs"]},
            },
            {"_id": 0},
        )
        if not other:
            await _update_resource_status_by_name(
                result["incident_id"], ressource_name, "verfuegbar"
            )

    if existing_ressource and existing_ressource != new_ressource:
        await _release_if_free(existing_ressource)
    if new_ressource and new_status in ("zugewiesen", "unterwegs"):
        await _update_resource_status_by_name(
            result["incident_id"], new_ressource, "im_einsatz"
        )
    if new_status == "abgeschlossen" and new_ressource:
        await _release_if_free(new_ressource)

    # Bett automatisch freigeben wenn Transport abgeschlossen
    if new_status == "abgeschlossen" and result.get("patient_id"):
        await _release_bett_for_patient(result["patient_id"])

    return result


@api_router.delete("/transports/{transport_id}", status_code=204)
async def delete_transport(transport_id: str):
    result = await db.transports.delete_one({"id": transport_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transport nicht gefunden")
    return None


# ---------------------------------------------------------------------------
# Ressourcen
# ---------------------------------------------------------------------------

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


class ResourceBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=80)
    typ: TransportTyp
    kategorie: ResourceKategorie = "sonstiges"
    status: ResourceStatus = "verfuegbar"
    notiz: str = Field(default="", max_length=1000)
    abschnitt_id: Optional[str] = None


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    typ: Optional[TransportTyp] = None
    kategorie: Optional[ResourceKategorie] = None
    status: Optional[ResourceStatus] = None
    notiz: Optional[str] = None
    abschnitt_id: Optional[str] = None  # leer-string = entfernen


class Resource(ResourceBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


def _serialize_resource(doc: dict) -> dict:
    doc = {k: v for k, v in doc.items() if k != "_id"}
    for k in ("created_at", "updated_at"):
        if k in doc and isinstance(doc[k], datetime):
            doc[k] = iso(doc[k])
    return doc


async def _seed_default_resources(incident_id: str):
    existing = await db.resources.count_documents({"incident_id": incident_id})
    if existing > 0:
        return
    docs = []
    for defn in DEFAULT_RESOURCES:
        r = Resource(incident_id=incident_id, **defn)
        d = r.model_dump()
        for k in ("created_at", "updated_at"):
            if isinstance(d.get(k), datetime):
                d[k] = iso(d[k])
        docs.append(d)
    if docs:
        await db.resources.insert_many(docs)


async def _update_resource_status_by_name(incident_id: str, name: str, status: str):
    now = now_utc()
    await db.resources.update_one(
        {"incident_id": incident_id, "name": name},
        {"$set": {"status": status, "updated_at": iso(now)}},
    )


@api_router.get("/incidents/{incident_id}/resources", response_model=List[dict])
async def list_resources(incident_id: str, typ: Optional[str] = None, status: Optional[str] = None):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    # Lazy seed
    await _seed_default_resources(incident_id)
    query: dict = {"incident_id": incident_id}
    if typ:
        query["typ"] = {"$in": [v.strip() for v in typ.split(",") if v.strip()]}
    if status:
        query["status"] = {"$in": [v.strip() for v in status.split(",") if v.strip()]}
    cursor = db.resources.find(query, {"_id": 0}).sort([("typ", 1), ("name", 1)])
    return await cursor.to_list(500)


@api_router.post("/incidents/{incident_id}/resources", response_model=dict, status_code=201)
async def create_resource(incident_id: str, payload: ResourceCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    r = Resource(incident_id=incident_id, **payload.model_dump(exclude_none=True))
    d = r.model_dump()
    for k in ("created_at", "updated_at"):
        if isinstance(d.get(k), datetime):
            d[k] = iso(d[k])
    await db.resources.insert_one(d)
    return _serialize_resource(d)


@api_router.patch("/resources/{resource_id}", response_model=dict)
async def update_resource(resource_id: str, payload: ResourceUpdate):
    upd = payload.model_dump(exclude_none=True)
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    upd["updated_at"] = iso(now_utc())
    res = await db.resources.find_one_and_update(
        {"id": resource_id},
        {"$set": upd},
        return_document=True,
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(status_code=404, detail="Ressource nicht gefunden")
    return res


@api_router.delete("/resources/{resource_id}", status_code=204)
async def delete_resource(resource_id: str):
    r = await db.resources.delete_one({"id": resource_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ressource nicht gefunden")
    return None


# ---------------------------------------------------------------------------
# Schritt 10: Einsatzabschnitte
# ---------------------------------------------------------------------------

ABSCHNITT_FARBEN = ["red", "orange", "yellow", "green", "teal", "blue", "indigo", "purple", "pink", "gray"]


class AbschnittBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=80)
    farbe: str = Field(default="blue", max_length=20)
    beschreibung: str = Field(default="", max_length=1000)
    aktiv: bool = True


class AbschnittCreate(AbschnittBase):
    pass


class AbschnittUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    farbe: Optional[str] = None
    beschreibung: Optional[str] = None
    aktiv: Optional[bool] = None


class Abschnitt(AbschnittBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    erstellt_um: datetime = Field(default_factory=now_utc)


def _serialize_abschnitt(doc: dict) -> dict:
    doc = {k: v for k, v in doc.items() if k != "_id"}
    if isinstance(doc.get("erstellt_um"), datetime):
        doc["erstellt_um"] = iso(doc["erstellt_um"])
    return doc


@api_router.get("/incidents/{incident_id}/abschnitte", response_model=List[dict])
async def list_abschnitte(incident_id: str, aktiv: Optional[bool] = None):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    query: dict = {"incident_id": incident_id}
    if aktiv is not None:
        query["aktiv"] = aktiv
    cursor = db.abschnitte.find(query, {"_id": 0}).sort("erstellt_um", 1)
    return await cursor.to_list(200)


@api_router.post("/incidents/{incident_id}/abschnitte", response_model=dict, status_code=201)
async def create_abschnitt(incident_id: str, payload: AbschnittCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    a = Abschnitt(incident_id=incident_id, **payload.model_dump(exclude_none=True))
    d = a.model_dump()
    if isinstance(d.get("erstellt_um"), datetime):
        d["erstellt_um"] = iso(d["erstellt_um"])
    await db.abschnitte.insert_one(d)
    return _serialize_abschnitt(d)


@api_router.get("/abschnitte/{abschnitt_id}", response_model=dict)
async def get_abschnitt(abschnitt_id: str):
    d = await db.abschnitte.find_one({"id": abschnitt_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Abschnitt nicht gefunden")
    return d


@api_router.patch("/abschnitte/{abschnitt_id}", response_model=dict)
async def update_abschnitt(abschnitt_id: str, payload: AbschnittUpdate):
    upd = payload.model_dump(exclude_none=True)
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    res = await db.abschnitte.find_one_and_update(
        {"id": abschnitt_id},
        {"$set": upd},
        return_document=True,
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(status_code=404, detail="Abschnitt nicht gefunden")
    return res


@api_router.delete("/abschnitte/{abschnitt_id}", status_code=204)
async def delete_abschnitt(abschnitt_id: str):
    a = await db.abschnitte.find_one({"id": abschnitt_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Abschnitt nicht gefunden")
    # Bei laufendem Incident: nur deaktivieren, nicht loeschen
    inc = await db.incidents.find_one({"id": a["incident_id"]}, {"_id": 0})
    if inc and inc.get("status") in ("operativ", "geplant"):
        raise HTTPException(
            status_code=409,
            detail="Abschnitt kann bei laufendem Incident nur deaktiviert, nicht geloescht werden",
        )
    # Referenzen loesen
    await db.resources.update_many(
        {"abschnitt_id": abschnitt_id},
        {"$set": {"abschnitt_id": None}},
    )
    await db.betten.update_many(
        {"abschnitt_id": abschnitt_id},
        {"$set": {"abschnitt_id": None}},
    )
    await db.abschnitte.delete_one({"id": abschnitt_id})
    return None


# ---------------------------------------------------------------------------
# Schritt 11: Behandlungsbetten (UHS)
# ---------------------------------------------------------------------------

BettTyp = Literal["liegend", "sitzend", "schockraum", "beobachtung", "sonstiges"]
BettStatus = Literal["frei", "belegt", "gesperrt"]


class BettBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=60)
    typ: BettTyp = "liegend"
    status: BettStatus = "frei"
    abschnitt_id: Optional[str] = None
    notiz: str = Field(default="", max_length=500)


class BettCreate(BettBase):
    pass


class BettUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    typ: Optional[BettTyp] = None
    status: Optional[BettStatus] = None
    abschnitt_id: Optional[str] = None
    notiz: Optional[str] = None


class BettBulkCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    anzahl: int = Field(ge=1, le=50)
    typ: BettTyp = "liegend"
    praefix: str = Field(default="Bett", max_length=30)
    abschnitt_id: Optional[str] = None
    start_index: int = Field(default=1, ge=1)


class BettAssign(BaseModel):
    model_config = ConfigDict(extra="ignore")
    patient_id: str


class Bett(BettBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    patient_id: Optional[str] = None
    belegt_seit: Optional[datetime] = None
    erstellt_um: datetime = Field(default_factory=now_utc)


def _serialize_bett(doc: dict) -> dict:
    doc = {k: v for k, v in doc.items() if k != "_id"}
    for k in ("belegt_seit", "erstellt_um"):
        if k in doc and isinstance(doc[k], datetime):
            doc[k] = iso(doc[k])
    return doc


@api_router.get("/incidents/{incident_id}/betten", response_model=List[dict])
async def list_betten(
    incident_id: str,
    status: Optional[str] = None,
    abschnitt_id: Optional[str] = None,
):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    query: dict = {"incident_id": incident_id}
    if status:
        query["status"] = {"$in": [v.strip() for v in status.split(",") if v.strip()]}
    if abschnitt_id:
        query["abschnitt_id"] = abschnitt_id
    cursor = db.betten.find(query, {"_id": 0}).sort("erstellt_um", 1)
    return await cursor.to_list(500)


@api_router.post("/incidents/{incident_id}/betten", response_model=dict, status_code=201)
async def create_bett(incident_id: str, payload: BettCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    b = Bett(incident_id=incident_id, **payload.model_dump(exclude_none=True))
    d = b.model_dump()
    for k in ("belegt_seit", "erstellt_um"):
        if isinstance(d.get(k), datetime):
            d[k] = iso(d[k])
    await db.betten.insert_one(d)
    return _serialize_bett(d)


@api_router.post("/incidents/{incident_id}/betten/bulk", response_model=List[dict], status_code=201)
async def create_betten_bulk(incident_id: str, payload: BettBulkCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    created = []
    for i in range(payload.anzahl):
        b = Bett(
            incident_id=incident_id,
            name=f"{payload.praefix} {payload.start_index + i}",
            typ=payload.typ,
            abschnitt_id=payload.abschnitt_id,
        )
        d = b.model_dump()
        for k in ("belegt_seit", "erstellt_um"):
            if isinstance(d.get(k), datetime):
                d[k] = iso(d[k])
        await db.betten.insert_one(d)
        created.append(_serialize_bett(d))
    return created


@api_router.get("/betten/{bett_id}", response_model=dict)
async def get_bett(bett_id: str):
    d = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    return d


@api_router.patch("/betten/{bett_id}", response_model=dict)
async def update_bett(bett_id: str, payload: BettUpdate):
    upd = payload.model_dump(exclude_none=True)
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    res = await db.betten.find_one_and_update(
        {"id": bett_id},
        {"$set": upd},
        return_document=True,
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    return res


@api_router.delete("/betten/{bett_id}", status_code=204)
async def delete_bett(bett_id: str):
    b = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    if not b:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    if b.get("status") == "belegt" or b.get("patient_id"):
        raise HTTPException(
            status_code=409,
            detail="Belegtes Bett kann nicht geloescht werden. Erst Patient entfernen.",
        )
    await db.betten.delete_one({"id": bett_id})
    return None


@api_router.post("/betten/{bett_id}/assign", response_model=dict)
async def assign_bett(bett_id: str, payload: BettAssign):
    bett = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    if not bett:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    if bett.get("status") == "gesperrt":
        raise HTTPException(status_code=409, detail="Bett ist gesperrt")
    if bett.get("status") == "belegt" and bett.get("patient_id") != payload.patient_id:
        raise HTTPException(status_code=409, detail="Bett bereits belegt")

    patient = await db.patients.find_one({"id": payload.patient_id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    if patient.get("incident_id") != bett.get("incident_id"):
        raise HTTPException(status_code=400, detail="Patient gehoert nicht zu diesem Incident")

    now = now_utc()
    # Falls Patient bereits in einem anderen Bett: dort freigeben
    if patient.get("bett_id") and patient["bett_id"] != bett_id:
        await db.betten.update_one(
            {"id": patient["bett_id"]},
            {"$set": {"status": "frei", "patient_id": None, "belegt_seit": None}},
        )

    await db.betten.update_one(
        {"id": bett_id},
        {"$set": {
            "status": "belegt",
            "patient_id": payload.patient_id,
            "belegt_seit": iso(now),
        }},
    )
    await db.patients.update_one(
        {"id": payload.patient_id},
        {"$set": {"bett_id": bett_id, "updated_at": iso(now)}},
    )
    out = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    return out


@api_router.post("/betten/{bett_id}/release", response_model=dict)
async def release_bett(bett_id: str):
    bett = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    if not bett:
        raise HTTPException(status_code=404, detail="Bett nicht gefunden")
    patient_id = bett.get("patient_id")
    await db.betten.update_one(
        {"id": bett_id},
        {"$set": {"status": "frei", "patient_id": None, "belegt_seit": None}},
    )
    if patient_id:
        await db.patients.update_one(
            {"id": patient_id, "bett_id": bett_id},
            {"$set": {"bett_id": None, "updated_at": iso(now_utc())}},
        )
    out = await db.betten.find_one({"id": bett_id}, {"_id": 0})
    return out


async def _release_bett_for_patient(patient_id: str):
    """Wird beim Transport-Abschluss oder Fallabschluss aufgerufen."""
    b = await db.betten.find_one({"patient_id": patient_id, "status": "belegt"}, {"_id": 0})
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


# ---------------------------------------------------------------------------
# Kommunikation (Messages)
# ---------------------------------------------------------------------------


class MessageBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = Field(min_length=1, max_length=4000)
    prioritaet: MessagePrio = "normal"
    kategorie: MessageKat = "info"
    von: str = Field(default="", max_length=80)


class MessageCreate(MessageBase):
    pass


class Message(MessageBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    quittiert_at: Optional[datetime] = None
    quittiert_von: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)


def _serialize_message(doc: dict) -> dict:
    doc = {k: v for k, v in doc.items() if k != "_id"}
    for k in ("created_at", "quittiert_at"):
        if k in doc and isinstance(doc[k], datetime):
            doc[k] = iso(doc[k])
    return doc


@api_router.get("/incidents/{incident_id}/messages", response_model=List[dict])
async def list_messages(incident_id: str, open_only: bool = False):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    query: dict = {"incident_id": incident_id}
    if open_only:
        query["quittiert_at"] = None
    cursor = db.messages.find(query, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(500)


@api_router.post("/incidents/{incident_id}/messages", response_model=dict, status_code=201)
async def create_message(incident_id: str, payload: MessageCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    m = Message(incident_id=incident_id, **payload.model_dump(exclude_none=True))
    d = m.model_dump()
    for k in ("created_at", "quittiert_at"):
        if isinstance(d.get(k), datetime):
            d[k] = iso(d[k])
    await db.messages.insert_one(d)
    return _serialize_message(d)


@api_router.post("/messages/{message_id}/ack", response_model=dict)
async def ack_message(message_id: str, by: Optional[str] = None):
    now = now_utc()
    result = await db.messages.find_one_and_update(
        {"id": message_id},
        {"$set": {"quittiert_at": iso(now), "quittiert_von": by or "Einsatzleiter"}},
        return_document=True,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    return result


@api_router.delete("/messages/{message_id}", status_code=204)
async def delete_message(message_id: str):
    r = await db.messages.delete_one({"id": message_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    return None


# ---------------------------------------------------------------------------
# Konflikte (Auto-Detection, nicht persistiert)
# ---------------------------------------------------------------------------


@api_router.get("/incidents/{incident_id}/konflikte", response_model=List[dict])
async def detect_konflikte(incident_id: str):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    now = now_utc()
    konflikte: list[dict] = []

    # Regel 1: Patient S1 wartend > 5 Min
    patients = await db.patients.find(
        {"incident_id": incident_id, "status": "wartend", "sichtung": "S1"},
        {"_id": 0},
    ).to_list(500)
    for p in patients:
        created = parse_iso(p.get("created_at"))
        if created and (now - created).total_seconds() > 300:
            konflikte.append({
                "id": f"p-wartend-{p['id']}",
                "typ": "patient_kritisch_wartet",
                "schwere": "rot",
                "titel": f"S1-Patient wartet ({p['kennung']})",
                "beschreibung": f"S1-Patient {p['kennung']} ist seit {int((now - created).total_seconds() // 60)} Min. im Status 'wartend'.",
                "bezug_typ": "patient",
                "bezug_id": p["id"],
                "bezug_label": p["kennung"],
                "seit": iso(created),
            })

    # Regel 2: Transport offen ohne Ressource > 10 Min
    tnow = await db.transports.find(
        {"incident_id": incident_id, "status": "offen", "ressource": None},
        {"_id": 0},
    ).to_list(500)
    for t in tnow:
        created = parse_iso(t.get("created_at"))
        if created and (now - created).total_seconds() > 600:
            konflikte.append({
                "id": f"t-offen-{t['id']}",
                "typ": "transport_ohne_ressource",
                "schwere": "gelb",
                "titel": "Transport ohne Ressource",
                "beschreibung": f"Transport {t.get('patient_kennung') or 'ohne Patient'} wartet seit {int((now - created).total_seconds() // 60)} Min. auf eine Ressource.",
                "bezug_typ": "transport",
                "bezug_id": t["id"],
                "bezug_label": t.get("patient_kennung") or "Transport",
                "seit": iso(created),
            })

    # Regel 3: Transport unterwegs > 60 Min
    tunterwegs = await db.transports.find(
        {"incident_id": incident_id, "status": "unterwegs"},
        {"_id": 0},
    ).to_list(500)
    for t in tunterwegs:
        start = parse_iso(t.get("gestartet_at"))
        if start and (now - start).total_seconds() > 3600:
            konflikte.append({
                "id": f"t-lang-{t['id']}",
                "typ": "transport_lang_unterwegs",
                "schwere": "gelb",
                "titel": "Transport lange unterwegs",
                "beschreibung": f"Transport {t.get('patient_kennung') or ''} ({t.get('ressource') or 'unbekannt'}) bereits {int((now - start).total_seconds() // 60)} Min. unterwegs.",
                "bezug_typ": "transport",
                "bezug_id": t["id"],
                "bezug_label": t.get("patient_kennung") or "Transport",
                "seit": iso(start),
            })

    # Regel 4: Kritische Meldungen unquittiert
    mhigh = await db.messages.find(
        {
            "incident_id": incident_id,
            "prioritaet": "kritisch",
            "quittiert_at": None,
        },
        {"_id": 0},
    ).to_list(200)
    for m in mhigh:
        konflikte.append({
            "id": f"m-unack-{m['id']}",
            "typ": "kritische_meldung_offen",
            "schwere": "rot",
            "titel": "Kritische Meldung unquittiert",
            "beschreibung": m["text"][:160],
            "bezug_typ": "message",
            "bezug_id": m["id"],
            "bezug_label": m.get("von") or "System",
            "seit": m.get("created_at"),
        })

    # Sortiert: rot > gelb > info
    order = {"rot": 0, "gelb": 1, "info": 2}
    konflikte.sort(key=lambda k: order.get(k["schwere"], 9))
    return konflikte


# ---------------------------------------------------------------------------
# Schritt 09: Auswertung & Abschluss
# ---------------------------------------------------------------------------


def _duration_ms(a, b):
    if not a or not b:
        return None
    return (parse_iso(b) - parse_iso(a)).total_seconds() * 1000


def _avg_minutes(values):
    nums = [v for v in values if v is not None and v > 0]
    if not nums:
        return 0
    return round(sum(nums) / len(nums) / 1000 / 60, 1)


@api_router.get("/incidents/{incident_id}/auswertung", response_model=dict)
async def get_auswertung(incident_id: str):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    patients = await db.patients.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    transports = await db.transports.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    messages = await db.messages.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    resources = await db.resources.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)
    abschnitte = await db.abschnitte.find({"incident_id": incident_id}, {"_id": 0}).to_list(200)
    betten = await db.betten.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)

    # A Patienten
    sichtung_counts = {"S1": 0, "S2": 0, "S3": 0, "S0": 0, "ohne": 0}
    status_counts = {k: 0 for k in ["wartend", "in_behandlung", "transportbereit", "uebergeben", "entlassen"]}
    wartezeiten = []
    behandlungsdauern = []
    for p in patients:
        if p.get("sichtung") in sichtung_counts:
            sichtung_counts[p["sichtung"]] += 1
        else:
            sichtung_counts["ohne"] += 1
        st = p.get("status")
        if st in status_counts:
            status_counts[st] += 1
        wartezeiten.append(_duration_ms(p.get("created_at"), p.get("sichtung_at")))
        behandlungsdauern.append(_duration_ms(p.get("behandlung_start_at"), p.get("fallabschluss_at")))

    block_a = {
        "total": len(patients),
        "sichtung": sichtung_counts,
        "status": status_counts,
        "wartezeit_min_avg": _avg_minutes(wartezeiten),
        "behandlungsdauer_min_avg": _avg_minutes(behandlungsdauern),
    }

    # Schritt 11: Bett-KPIs in Block A
    bett_belegt = [b for b in betten if b.get("status") == "belegt"]
    bett_belegungsdauern = []
    now_dt = now_utc()
    for b in betten:
        if b.get("belegt_seit"):
            bett_belegungsdauern.append(_duration_ms(b["belegt_seit"], iso(now_dt)))
    max_gleichzeitig = len(bett_belegt)  # naive: aktuell gleichzeitig belegte
    total_betten = len(betten)
    auslastung = round(100.0 * len(bett_belegt) / total_betten, 1) if total_betten else 0.0
    block_a["betten"] = {
        "total": total_betten,
        "frei": sum(1 for b in betten if b.get("status") == "frei"),
        "belegt": len(bett_belegt),
        "gesperrt": sum(1 for b in betten if b.get("status") == "gesperrt"),
        "auslastung_pct": auslastung,
        "belegungsdauer_min_avg": _avg_minutes(bett_belegungsdauern),
        "max_gleichzeitig": max_gleichzeitig,
    }

    # B Transporte
    t_by_status = {"offen": 0, "zugewiesen": 0, "unterwegs": 0, "abgeschlossen": 0}
    t_by_typ = {"intern": 0, "extern": 0}
    t_dauern = []
    for t in transports:
        if t.get("status") in t_by_status:
            t_by_status[t["status"]] += 1
        if t.get("typ") in t_by_typ:
            t_by_typ[t["typ"]] += 1
        t_dauern.append(_duration_ms(t.get("gestartet_at"), t.get("abgeschlossen_at")))
    block_b = {
        "total": len(transports),
        "status": t_by_status,
        "typ": t_by_typ,
        "fahrtdauer_min_avg": _avg_minutes(t_dauern),
    }

    # C Meldungen
    m_prio = {"kritisch": 0, "dringend": 0, "normal": 0}
    m_offen = 0
    ack_dauern = []
    for m in messages:
        if m.get("prioritaet") in m_prio:
            m_prio[m["prioritaet"]] += 1
        if not m.get("quittiert_at"):
            m_offen += 1
        ack_dauern.append(_duration_ms(m.get("created_at"), m.get("quittiert_at")))
    block_c = {
        "total": len(messages),
        "prioritaet": m_prio,
        "offen": m_offen,
        "quittier_dauer_min_avg": _avg_minutes(ack_dauern),
    }

    # D Ressourcen
    r_status = {"verfuegbar": 0, "im_einsatz": 0, "wartung": 0, "offline": 0}
    for r in resources:
        if r.get("status") in r_status:
            r_status[r["status"]] += 1
    ohne_abschnitt = [r for r in resources if not r.get("abschnitt_id")]
    block_d = {
        "total": len(resources),
        "status": r_status,
        "ohne_abschnitt": len(ohne_abschnitt),
        "ohne_abschnitt_pct": round(100.0 * len(ohne_abschnitt) / len(resources), 1) if resources else 0.0,
    }

    # Schritt 10: Abschnitte-Zusammenfassung als eigener Block
    abschnitte_summary = []
    for a in abschnitte:
        a_res = [r for r in resources if r.get("abschnitt_id") == a["id"]]
        a_bet = [b for b in betten if b.get("abschnitt_id") == a["id"]]
        im_einsatz = sum(1 for r in a_res if r.get("status") == "im_einsatz")
        belegt = sum(1 for b in a_bet if b.get("status") == "belegt")
        # Ampel: rot = alle Ressourcen im Einsatz, gelb = teilweise, gruen = alle verfuegbar
        if not a_res:
            ampel = "gray"
        elif im_einsatz == len(a_res):
            ampel = "red"
        elif im_einsatz > 0:
            ampel = "yellow"
        else:
            ampel = "green"
        abschnitte_summary.append({
            "id": a["id"],
            "name": a["name"],
            "farbe": a.get("farbe", "blue"),
            "aktiv": a.get("aktiv", True),
            "ressourcen_total": len(a_res),
            "ressourcen_im_einsatz": im_einsatz,
            "betten_total": len(a_bet),
            "betten_belegt": belegt,
            "ampel": ampel,
        })
    block_g = {
        "total": len(abschnitte),
        "aktiv": sum(1 for a in abschnitte if a.get("aktiv", True)),
        "abschnitte": abschnitte_summary,
    }

    # E Konflikte
    konflikte = await detect_konflikte(incident_id)
    block_e = {
        "total": len(konflikte),
        "rot": sum(1 for k in konflikte if k["schwere"] == "rot"),
        "gelb": sum(1 for k in konflikte if k["schwere"] == "gelb"),
    }

    # F Metadaten
    end_ref = inc.get("end_at") or iso(now_utc())
    dauer_ms = _duration_ms(inc.get("start_at"), end_ref)
    block_f = {
        "incident_id": inc["id"],
        "name": inc["name"],
        "typ": inc.get("typ"),
        "ort": inc.get("ort"),
        "status": inc.get("status"),
        "demo": bool(inc.get("demo")),
        "start_at": inc.get("start_at"),
        "end_at": inc.get("end_at"),
        "einsatzdauer_min": round((dauer_ms or 0) / 1000 / 60, 1),
    }

    return {"A_patienten": block_a, "B_transporte": block_b, "C_kommunikation": block_c,
            "D_ressourcen": block_d, "E_konflikte": block_e, "F_metadaten": block_f,
            "G_abschnitte": block_g}


@api_router.get("/incidents/{incident_id}/abschluss-check", response_model=dict)
async def get_abschluss_check(incident_id: str):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    patients = await db.patients.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    transports = await db.transports.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    messages = await db.messages.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    resources = await db.resources.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)
    abschnitte = await db.abschnitte.find({"incident_id": incident_id}, {"_id": 0}).to_list(200)
    betten = await db.betten.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)

    blockers: list[dict] = []
    warnings: list[dict] = []

    # Blocker: Patienten noch nicht abgeschlossen
    offene = [p for p in patients if p.get("status") in ("wartend", "in_behandlung", "transportbereit")]
    if offene:
        blockers.append({
            "id": "offene_patienten",
            "titel": f"{len(offene)} offene Patienten",
            "beschreibung": "Alle Patienten muessen abgeschlossen (uebergeben oder entlassen) sein.",
            "typ": "patienten",
            "count": len(offene),
        })

    # Blocker: Transporte unterwegs
    unterwegs = [t for t in transports if t.get("status") in ("offen", "zugewiesen", "unterwegs")]
    if unterwegs:
        blockers.append({
            "id": "offene_transporte",
            "titel": f"{len(unterwegs)} offene Transporte",
            "beschreibung": "Alle Transporte muessen abgeschlossen sein.",
            "typ": "transporte",
            "count": len(unterwegs),
        })

    # Blocker: Unquittierte kritische Meldungen
    krit = [m for m in messages if m.get("prioritaet") == "kritisch" and not m.get("quittiert_at")]
    if krit:
        blockers.append({
            "id": "offene_kritisch",
            "titel": f"{len(krit)} kritische Meldungen unquittiert",
            "beschreibung": "Kritische Meldungen muessen vor Abschluss quittiert sein.",
            "typ": "meldungen",
            "count": len(krit),
        })

    # Warnung: Unquittierte dringende Meldungen
    drng = [m for m in messages if m.get("prioritaet") == "dringend" and not m.get("quittiert_at")]
    if drng:
        warnings.append({
            "id": "offene_dringend",
            "titel": f"{len(drng)} dringende Meldungen unquittiert",
            "beschreibung": "Empfehlung: vor Abschluss quittieren.",
            "typ": "meldungen",
            "count": len(drng),
        })

    # Warnung: Patienten ohne Sichtung
    ohne_s = [p for p in patients if not p.get("sichtung")]
    if ohne_s:
        warnings.append({
            "id": "ohne_sichtung",
            "titel": f"{len(ohne_s)} Patienten ohne Sichtung",
            "beschreibung": "Sichtung nachtragen fuer vollstaendigen Bericht.",
            "typ": "patienten",
            "count": len(ohne_s),
        })

    # Warnung: Keine Meldungen erfasst
    if not messages:
        warnings.append({
            "id": "keine_meldungen",
            "titel": "Keine Meldungen erfasst",
            "beschreibung": "Fuer vollstaendige Dokumentation sollten Meldungen erfasst sein.",
            "typ": "meldungen",
            "count": 0,
        })

    # Schritt 12: Blocker - aktive Patienten ohne Bett und ohne Transport
    transport_patient_ids = {t.get("patient_id") for t in transports if t.get("patient_id")}
    aktiv_ohne_bett_ohne_transport = []
    for p in patients:
        if p.get("status") in ("in_behandlung", "transportbereit"):
            if not p.get("bett_id") and p.get("id") not in transport_patient_ids:
                aktiv_ohne_bett_ohne_transport.append(p)
    if aktiv_ohne_bett_ohne_transport:
        blockers.append({
            "id": "aktive_ohne_bett_transport",
            "titel": f"{len(aktiv_ohne_bett_ohne_transport)} aktive Patienten ohne Bett und ohne Transport",
            "beschreibung": "Aktiver Patient muss einem Bett zugewiesen oder in Transport sein.",
            "typ": "patienten",
            "count": len(aktiv_ohne_bett_ohne_transport),
        })

    # Schritt 10: Warnung - Ressourcen ohne Abschnitt > 20%
    if resources:
        ohne_abschnitt = [r for r in resources if not r.get("abschnitt_id")]
        pct = 100.0 * len(ohne_abschnitt) / len(resources)
        if pct > 20:
            warnings.append({
                "id": "ressourcen_ohne_abschnitt",
                "titel": f"{len(ohne_abschnitt)} Ressourcen ohne Abschnitt ({pct:.0f}%)",
                "beschreibung": "Empfehlung: Ressourcen einem Einsatzabschnitt zuweisen.",
                "typ": "ressourcen",
                "count": len(ohne_abschnitt),
            })

    # Schritt 10: Warnung - Abschnitte ohne Ressourcen
    leere_abschnitte = []
    for a in abschnitte:
        if not any(r.get("abschnitt_id") == a["id"] for r in resources):
            leere_abschnitte.append(a)
    if leere_abschnitte:
        warnings.append({
            "id": "abschnitte_leer",
            "titel": f"{len(leere_abschnitte)} Abschnitte ohne Ressourcen",
            "beschreibung": "Diese Abschnitte haben keine zugeordneten Ressourcen: "
                            + ", ".join(a["name"] for a in leere_abschnitte[:3])
                            + ("…" if len(leere_abschnitte) > 3 else ""),
            "typ": "abschnitte",
            "count": len(leere_abschnitte),
        })

    # Schritt 11: Warnung - Betten gesperrt/nie belegt
    nie_belegt = [b for b in betten if not b.get("belegt_seit") and b.get("status") == "gesperrt"]
    if nie_belegt:
        warnings.append({
            "id": "betten_nie_belegt",
            "titel": f"{len(nie_belegt)} Betten gesperrt und nie belegt",
            "beschreibung": "Diese Betten wurden wahrscheinlich nicht benoetigt.",
            "typ": "betten",
            "count": len(nie_belegt),
        })

    return {
        "incident_status": inc.get("status"),
        "bereit_fuer_abschluss": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
    }


@api_router.get("/incidents/{incident_id}/report", response_model=dict)
async def get_report(incident_id: str):
    """Liefert die 14 Kapitel des Abschlussberichts als strukturierte Daten."""
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    auswertung = await get_auswertung(incident_id)
    patients = await db.patients.find({"incident_id": incident_id}, {"_id": 0}).sort("kennung", 1).to_list(2000)
    transports = await db.transports.find({"incident_id": incident_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    messages = await db.messages.find({"incident_id": incident_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    resources = await db.resources.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)
    abschnitte = await db.abschnitte.find({"incident_id": incident_id}, {"_id": 0}).to_list(200)
    betten = await db.betten.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)

    kapitel = [
        {"nr": 1, "titel": "Einsatzgrunddaten", "inhalt": {
            "name": inc["name"], "typ": inc.get("typ"), "ort": inc.get("ort"),
            "start": inc.get("start_at"), "ende": inc.get("end_at"),
            "dauer_min": auswertung["F_metadaten"]["einsatzdauer_min"],
            "demo": inc.get("demo", False),
        }},
        {"nr": 2, "titel": "Organisation & Rollen", "inhalt": {
            "einsatzleiter": "Einsatzleiter (Rolle)",
            "rollen": ["Einsatzleiter", "Sanitaeter / Helfer", "Dokumentar"],
            "abschnitte": [
                {"id": a["id"], "name": a["name"], "farbe": a.get("farbe", "blue"), "aktiv": a.get("aktiv", True)}
                for a in abschnitte
            ],
        }},
        {"nr": 3, "titel": "Patientenuebersicht", "inhalt": auswertung["A_patienten"]},
        {"nr": 4, "titel": "Patientenliste", "inhalt": {"patienten": patients}},
        {"nr": 5, "titel": "Sichtungsverteilung", "inhalt": auswertung["A_patienten"]["sichtung"]},
        {"nr": 6, "titel": "Behandlungszeiten", "inhalt": {
            "wartezeit_min_avg": auswertung["A_patienten"]["wartezeit_min_avg"],
            "behandlungsdauer_min_avg": auswertung["A_patienten"]["behandlungsdauer_min_avg"],
        }},
        {"nr": 7, "titel": "Transporte", "inhalt": {"transporte": transports, "summary": auswertung["B_transporte"]}},
        {"nr": 8, "titel": "Ressourcen", "inhalt": {"ressourcen": resources, "summary": auswertung["D_ressourcen"], "abschnitte": auswertung["G_abschnitte"], "betten": auswertung["A_patienten"].get("betten", {}), "bettliste": betten}},
        {"nr": 9, "titel": "Kommunikation", "inhalt": {"meldungen": messages, "summary": auswertung["C_kommunikation"]}},
        {"nr": 10, "titel": "Konflikte & Blocker", "inhalt": auswertung["E_konflikte"]},
        {"nr": 11, "titel": "Besondere Vorkommnisse", "inhalt": {
            "text": inc.get("meta", {}).get("besondere_vorkommnisse", "Keine besonderen Vorkommnisse dokumentiert."),
        }},
        {"nr": 12, "titel": "Nachbearbeitung & Anmerkungen", "inhalt": {
            "text": inc.get("meta", {}).get("nachbearbeitung", ""),
        }},
        {"nr": 13, "titel": "Freigabe", "inhalt": {
            "bereit_fuer_abschluss": inc.get("status") == "abgeschlossen",
            "freigegeben_von": inc.get("meta", {}).get("freigegeben_von"),
            "freigabe_at": inc.get("meta", {}).get("freigabe_at"),
        }},
        {"nr": 14, "titel": "Anhaenge & Quellen", "inhalt": {
            "quellen": "Generiert aus ELS-MHD Systemdaten.",
            "generiert_at": iso(now_utc()),
        }},
    ]

    return {"incident": inc, "kapitel": kapitel, "generiert_at": iso(now_utc())}


class ReportVersionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    freigegeben_von: Optional[str] = None
    kommentar: str = Field(default="", max_length=2000)


@api_router.get("/incidents/{incident_id}/report-versions", response_model=List[dict])
async def list_report_versions(incident_id: str):
    cursor = db.report_versions.find({"incident_id": incident_id}, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(200)


@api_router.post("/incidents/{incident_id}/report-versions", response_model=dict, status_code=201)
async def create_report_version(incident_id: str, payload: ReportVersionCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    count = await db.report_versions.count_documents({"incident_id": incident_id})
    report = await get_report(incident_id)
    doc = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "version": count + 1,
        "freigegeben_von": payload.freigegeben_von or "Einsatzleiter",
        "kommentar": payload.kommentar,
        "snapshot": report,
        "created_at": iso(now_utc()),
    }
    await db.report_versions.insert_one(doc)

    # Freigabe-Metadaten im Incident ablegen
    await db.incidents.update_one(
        {"id": incident_id},
        {"$set": {
            "meta.freigegeben_von": doc["freigegeben_von"],
            "meta.freigabe_at": doc["created_at"],
            "updated_at": iso(now_utc()),
        }}
    )
    return {k: v for k, v in doc.items() if k != "_id"}


class PatchMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    besondere_vorkommnisse: Optional[str] = None
    nachbearbeitung: Optional[str] = None


@api_router.patch("/incidents/{incident_id}/meta", response_model=dict)
async def patch_incident_meta(incident_id: str, payload: PatchMeta):
    upd = {f"meta.{k}": v for k, v in payload.model_dump(exclude_none=True).items()}
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    upd["updated_at"] = iso(now_utc())
    result = await db.incidents.find_one_and_update(
        {"id": incident_id}, {"$set": upd}, return_document=True, projection={"_id": 0}
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    return result


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def run_migrations():
    """
    One-time Migrationen. Idempotent gestaltet.
    - S4 -> S0 (Sichtungsstufen-Umbenennung)
    """
    try:
        result = await db.patients.update_many(
            {"sichtung": "S4"},
            {"$set": {"sichtung": "S0"}},
        )
        if result.modified_count:
            logger.info("Migration: %d Patient(en) von S4 nach S0 umbenannt", result.modified_count)
    except Exception as exc:  # pragma: no cover
        logger.exception("Migration fehlgeschlagen: %s", exc)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
