"""System-Eintraege fuer das Funktagebuch (Schritt 13)."""
import uuid
from typing import Optional

from core.db import db
from core.time import iso, now_utc


async def log_system_entry(
    incident_id: str,
    text: str,
    funk_typ: str = "system",
    prioritaet: str = "normal",
    kategorie: str = "info",
    absender: str = "System",
    empfaenger: str = "Funktagebuch",
    abschnitt_id: Optional[str] = None,
    transport_id: Optional[str] = None,
    ressource_id: Optional[str] = None,
    patient_id: Optional[str] = None,
):
    """Schreibt einen automatischen Funktagebuch-Eintrag.
    Systemeintraege sind unveraenderlich (siehe messages.py).
    """
    doc = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "text": text,
        "funk_typ": funk_typ,
        "prioritaet": prioritaet,
        "kategorie": kategorie,
        "von": absender,
        "absender": absender,
        "empfaenger": empfaenger,
        "abschnitt_id": abschnitt_id,
        "transport_id": transport_id,
        "ressource_id": ressource_id,
        "patient_id": patient_id,
        "erfasst_von": "System",
        "erfasst_rolle": "system",
        "quelle": "system",
        "quittiert_at": None,
        "quittiert_von": None,
        "bestaetigt_at": None,
        "bestaetigt_von": None,
        "finalisiert": True,
        "finalisiert_at": iso(now_utc()),
        "finalisiert_von": "System",
        "created_at": iso(now_utc()),
    }
    await db.messages.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}
