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
        "version": "0.5.0",
        "step": "05 – Transportuebersicht",
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
    logger.info("Demo-Incident erstellt: %s (%s)", obj.name, obj.id)
    return serialize_incident(doc)


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
    # Zugehoerige Patienten und Transporte mit entfernen
    await db.patients.delete_many({"incident_id": incident_id})
    await db.transports.delete_many({"incident_id": incident_id})
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
    return result


@api_router.delete("/transports/{transport_id}", status_code=204)
async def delete_transport(transport_id: str):
    result = await db.transports.delete_one({"id": transport_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transport nicht gefunden")
    return None


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
