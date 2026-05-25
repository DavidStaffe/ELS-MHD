"""All Pydantic models for the ELS-MHD API."""

from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, Field, ConfigDict

from core.time import now_utc
from core.types import (
    IncidentTyp,
    IncidentStatus,
    SichtungStufe,
    PatientStatus,
    PatientVerbleib,
    TransportTyp,
    TransportZiel,
    TransportStatus,
    FallabschlussTyp,
    ResourceKategorie,
    ResourceStatus,
    MessagePrio,
    MessageKat,
    FunkTyp,
    FunkQuelle,
    BettTyp,
    BettStatus,
)


# --- Incidents --------------------------------------------------------------


class IncidentBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=2, max_length=120)
    typ: IncidentTyp = "veranstaltung"
    ort: str = Field(min_length=0, max_length=180, default="")
    beschreibung: str = Field(default="", max_length=2000)
    ort_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    ort_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    ort_zoom: Optional[int] = Field(default=None, ge=1, le=22)


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
    ort_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    ort_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    ort_zoom: Optional[int] = Field(default=None, ge=1, le=22)


class Incident(IncidentBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: IncidentStatus = "operativ"
    demo: bool = False
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    # Divera-Polling-Status (Phase 3)
    divera_enabled: bool = False
    divera_last_poll_at: Optional[datetime] = None
    divera_last_poll_status: Optional[str] = None
    divera_last_match_count: Optional[int] = None


class IncidentMetaPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    besondere_vorkommnisse: Optional[str] = Field(default=None, max_length=4000)
    nachbearbeitung: Optional[str] = Field(default=None, max_length=4000)


# --- Patients ---------------------------------------------------------------


class PatientBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sichtung: Optional[SichtungStufe] = None
    status: PatientStatus = "wartend"
    verbleib: PatientVerbleib = "unbekannt"
    behandlung_ressource_id: Optional[str] = None
    notiz: str = Field(default="", max_length=4000)
    transport_typ: Optional[TransportTyp] = None
    fallabschluss_typ: Optional[FallabschlussTyp] = None
    bett_id: Optional[str] = None


class PatientCreate(PatientBase):
    sichtung: Optional[SichtungStufe] = None


class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sichtung: Optional[SichtungStufe] = None
    status: Optional[PatientStatus] = None
    verbleib: Optional[PatientVerbleib] = None
    behandlung_ressource_id: Optional[str] = None
    notiz: Optional[str] = None
    transport_typ: Optional[TransportTyp] = None
    fallabschluss_typ: Optional[FallabschlussTyp] = None
    bett_id: Optional[str] = None


class Patient(PatientBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    kennung: str
    behandlung_ressource_name: Optional[str] = None
    behandlung_ressource_events: List[dict] = Field(default_factory=list)
    sichtung_events: List[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    sichtung_at: Optional[datetime] = None
    behandlung_start_at: Optional[datetime] = None
    transport_angefordert_at: Optional[datetime] = None
    fallabschluss_at: Optional[datetime] = None
    wiedereroeffnet_at: List[datetime] = Field(default_factory=list)


# --- Transports -------------------------------------------------------------


class TransportBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    typ: TransportTyp
    ziel: TransportZiel
    ressource: Optional[str] = Field(default=None, max_length=80)
    notiz: str = Field(default="", max_length=1000)


class TransportCreate(TransportBase):
    patient_id: Optional[str] = None


class TransportUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    typ: Optional[TransportTyp] = None
    ziel: Optional[TransportZiel] = None
    ressource: Optional[str] = None
    notiz: Optional[str] = None
    status: Optional[TransportStatus] = None


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


# --- Resources --------------------------------------------------------------


class ResourceBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=80)
    kuerzel: Optional[str] = Field(default=None, max_length=4)
    typ: TransportTyp
    kategorie: ResourceKategorie = "sonstiges"
    status: ResourceStatus = "verfuegbar"
    notiz: str = Field(default="", max_length=1000)
    abschnitt_id: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    divera_id: Optional[str] = Field(default=None, max_length=64)
    fms_status: Optional[int] = Field(default=None, ge=0, le=9)


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    kuerzel: Optional[str] = Field(default=None, max_length=4)
    typ: Optional[TransportTyp] = None
    kategorie: Optional[ResourceKategorie] = None
    status: Optional[ResourceStatus] = None
    notiz: Optional[str] = None
    abschnitt_id: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    divera_id: Optional[str] = Field(default=None, max_length=64)
    fms_status: Optional[int] = Field(default=None, ge=0, le=9)


# --- Messages / Funktagebuch ------------------------------------------------


class MessageBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = Field(min_length=1, max_length=2000)
    prioritaet: MessagePrio = "normal"
    kategorie: MessageKat = "info"
    von: str = Field(default="", max_length=80)
    # Funktagebuch-Zusatzfelder (Schritt 13)
    funk_typ: FunkTyp = "lage"
    absender: str = Field(default="", max_length=120)
    empfaenger: str = Field(default="", max_length=120)
    abschnitt_id: Optional[str] = None
    transport_id: Optional[str] = None
    ressource_id: Optional[str] = None
    patient_id: Optional[str] = None
    erfasst_von: str = Field(default="", max_length=80)
    erfasst_rolle: str = Field(default="", max_length=40)


class MessageCreate(MessageBase):
    pass


class MessageUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: Optional[str] = None
    prioritaet: Optional[MessagePrio] = None
    kategorie: Optional[MessageKat] = None
    funk_typ: Optional[FunkTyp] = None
    absender: Optional[str] = None
    empfaenger: Optional[str] = None
    abschnitt_id: Optional[str] = None
    transport_id: Optional[str] = None
    ressource_id: Optional[str] = None
    patient_id: Optional[str] = None


class MessageAck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    quittiert_von: Optional[str] = Field(default=None, max_length=80)


class MessageConfirm(BaseModel):
    model_config = ConfigDict(extra="ignore")
    bestaetigt_von: Optional[str] = Field(default=None, max_length=80)


# --- Abschnitte (Schritt 10) ------------------------------------------------


class AbschnittBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=80)
    farbe: str = Field(default="blue", max_length=20)
    beschreibung: str = Field(default="", max_length=1000)
    aktiv: bool = True
    # Polygon: Liste von [lat, lng]-Paaren (Leaflet-Konvention).
    # Ein Polygon hat >= 3 Punkte; None = kein Polygon gezeichnet.
    polygon: Optional[List[List[float]]] = None


class AbschnittCreate(AbschnittBase):
    pass


class AbschnittUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    farbe: Optional[str] = None
    beschreibung: Optional[str] = None
    aktiv: Optional[bool] = None
    polygon: Optional[List[List[float]]] = None


class Abschnitt(AbschnittBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    erstellt_um: datetime = Field(default_factory=now_utc)


# --- Betten (Schritt 11) ----------------------------------------------------


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


# --- Report -----------------------------------------------------------------


class ReportVersionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    freigegeben_von: Optional[str] = Field(default=None, max_length=80)
    kommentar: Optional[str] = Field(default=None, max_length=400)
