"""DIVI-orientierte medizinische Dokumentation ohne Patienten-Klardaten.

Das Protokoll liegt eingebettet am Patienten: Archiv-Snapshots, Exporte und
Patientenlöschung folgen damit dem bestehenden Lebenszyklus. Änderungen
werden mit optimistischer Versionsprüfung und kompletter Historie gespeichert.
"""
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pymongo import ReturnDocument

from core.db import db
from core.identity import audit
from core.time import iso, now_utc
from services.realtime import publish_patient_event

router = APIRouter(prefix="/api", tags=["patient_protocol"])


class StrictSection(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Stammdaten(StrictSection):
    # Keine Namen, Anschrift, Krankenversicherung, Telefonnummern oder Signaturen.
    geburtsdatum: Optional[date] = None
    geschlecht: Optional[Literal["weiblich", "maennlich", "divers", "unbekannt"]] = None

    @field_validator("geburtsdatum")
    @classmethod
    def plausible_date(cls, value):
        if value and not (date(1900, 1, 1) <= value <= date.today()):
            raise ValueError("Geburtsdatum liegt außerhalb des plausiblen Bereichs")
        return value


class Anamnese(StrictSection):
    beschwerden: str = Field(default="", max_length=1000)
    symptome: str = Field(default="", max_length=800)
    allergien: str = Field(default="", max_length=500)
    medikation: str = Field(default="", max_length=800)
    vorgeschichte: str = Field(default="", max_length=800)
    letzte_mahlzeit: str = Field(default="", max_length=300)
    ereignis: str = Field(default="", max_length=800)
    risikofaktoren: str = Field(default="", max_length=500)
    schwangerschaft: str = Field(default="", max_length=200)


BefastChoice = Literal["nicht_erhoben", "unauffaellig", "auffaellig"]


class Erstbefund(StrictSection):
    x_blutung: str = Field(default="", max_length=600)
    a_atemweg: str = Field(default="", max_length=600)
    b_atmung: str = Field(default="", max_length=600)
    c_kreislauf: str = Field(default="", max_length=600)
    d_neurologie: str = Field(default="", max_length=600)
    e_exposition: str = Field(default="", max_length=600)
    befast_balance: BefastChoice = "nicht_erhoben"
    befast_eyes: BefastChoice = "nicht_erhoben"
    befast_face: BefastChoice = "nicht_erhoben"
    befast_arm: BefastChoice = "nicht_erhoben"
    befast_speech: BefastChoice = "nicht_erhoben"
    befast_time: str = Field(default="", max_length=80)


class Vitalwert(StrictSection):
    datum: Optional[date] = None
    zeit: str = Field(min_length=5, max_length=5, pattern=r"^\d{2}:\d{2}$")
    rr_sys: Optional[int] = Field(default=None, ge=30, le=300)
    rr_dia: Optional[int] = Field(default=None, ge=20, le=220)
    puls: Optional[int] = Field(default=None, ge=20, le=250)
    atemfrequenz: Optional[int] = Field(default=None, ge=0, le=80)
    spo2: Optional[int] = Field(default=None, ge=0, le=100)
    temperatur: Optional[float] = Field(default=None, ge=25, le=45)
    gcs: Optional[int] = Field(default=None, ge=3, le=15)
    blutzucker_mgdl: Optional[int] = Field(default=None, ge=10, le=1000)
    schmerz_nrs: Optional[int] = Field(default=None, ge=0, le=10)
    o2_gabe: Optional[bool] = None
    spo2_skala: Optional[Literal[1, 2]] = None

    @field_validator("zeit")
    @classmethod
    def clock_time(cls, value):
        hours, minutes = (int(x) for x in value.split(":"))
        if hours > 23 or minutes > 59:
            raise ValueError("Ungültige Uhrzeit")
        return value


class Verlauf(StrictSection):
    werte: list[Vitalwert] = Field(default_factory=list, max_length=48)
    notiz: str = Field(default="", max_length=2000)


class Massnahme(StrictSection):
    datum: Optional[date] = None
    zeit: str = Field(min_length=5, max_length=5, pattern=r"^\d{2}:\d{2}$")
    typ: Literal["allgemein", "atemweg", "beatmung", "kreislauf", "medikament", "immobilisation", "sonstiges"] = "allgemein"
    beschreibung: str = Field(min_length=1, max_length=500)
    dosis: str = Field(default="", max_length=100)
    appl_weg: str = Field(default="", max_length=100)
    wirkung: str = Field(default="", max_length=300)

    @field_validator("zeit")
    @classmethod
    def clock_time(cls, value):
        hours, minutes = (int(x) for x in value.split(":"))
        if hours > 23 or minutes > 59:
            raise ValueError("Ungültige Uhrzeit")
        return value


class Massnahmen(StrictSection):
    eintraege: list[Massnahme] = Field(default_factory=list, max_length=48)


class Uebergabe(StrictSection):
    datum: Optional[date] = None
    art: Literal["offen", "transport", "entlassen", "transportverweigerung", "uebergeben"] = "offen"
    zeit: str = Field(default="", max_length=5, pattern=r"^$|^\d{2}:\d{2}$")
    ziel: str = Field(default="", max_length=160)
    empfangende_funktion: str = Field(default="", max_length=160)
    sinnhaft: str = Field(default="", max_length=2000)
    aufklaerung_dokumentiert: bool = False
    verweigerung_bezeugt: bool = False
    # Keine Unterschriften-/Zeugen-Namen: die WebApp ist kein signierter Verzicht.


SECTION_MODELS = {
    "stammdaten": Stammdaten,
    "anamnese": Anamnese,
    "erstbefund": Erstbefund,
    "verlauf": Verlauf,
    "massnahmen": Massnahmen,
    "uebergabe": Uebergabe,
}


class ProtocolPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: Literal["stammdaten", "anamnese", "erstbefund", "verlauf", "massnahmen", "uebergabe"]
    data: dict = Field(default_factory=dict)
    expected_version: int = Field(ge=0)
    reason: str = Field(default="", max_length=300)


@router.patch("/patients/{patient_id}/protocol", response_model=dict)
async def update_patient_protocol(patient_id: str, payload: ProtocolPatch, request: Request):
    patient = request.state.record
    incident = request.state.incident
    if not patient or patient.get("id") != patient_id:
        raise HTTPException(404, "Patient nicht gefunden")
    if incident.get("status") == "abgeschlossen":
        raise HTTPException(409, "Archiv ist schreibgeschützt")
    if incident.get("status") == "geplant":
        raise HTTPException(409, "Dokumentation erst im operativen Incident möglich")

    try:
        validated = SECTION_MODELS[payload.section].model_validate(payload.data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False)) from exc
    section_data = validated.model_dump(mode="json")
    existing = patient.get("protokoll") or {}
    version = existing.get("version", 0)
    if payload.expected_version != version:
        raise HTTPException(409, "Protokoll wurde anderweitig geändert. Bitte aktualisieren.")

    # Spätdokumentation ist möglich, aber nach Fallabschluss begründungspflichtig.
    if patient.get("status") in {"uebergeben", "entlassen"} and len(payload.reason.strip()) < 10:
        raise HTTPException(422, "Nach Fallabschluss ist eine Begründung (mind. 10 Zeichen) nötig")

    now = iso(now_utc())
    new_version = version + 1
    new_protocol = {
        **existing,
        payload.section: section_data,
        "version": new_version,
        "updated_at": now,
    }
    old_section = existing.get(payload.section)
    history_entry = {
        "version": new_version,
        "at": now,
        "actor_id": request.state.user["id"],
        "section": payload.section,
        "before": old_section,
        "after": section_data,
        "reason": payload.reason.strip(),
    }
    constraint = {"id": patient_id, "incident_id": incident["id"]}
    if version:
        constraint["protokoll.version"] = version
    else:
        constraint["$or"] = [
            {"protokoll.version": {"$exists": False}},
            {"protokoll.version": 0},
        ]
    updated = await db.patients.find_one_and_update(
        constraint,
        {
            "$set": {"protokoll": new_protocol, "updated_at": now},
            "$push": {"protokoll_history": history_entry},
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(409, "Protokoll zwischenzeitlich geändert. Bitte aktualisieren.")
    await audit(
        request.state.user,
        "patient.protocol.update",
        incident_id=incident["id"],
        reason=payload.reason.strip() or None,
        data={"patient_id": patient_id, "section": payload.section, "version": new_version},
    )
    await publish_patient_event(
        incident["id"],
        {"kind": "patient", "action": "protocol_updated", "patient_id": patient_id, "ts": now},
    )
    return updated
