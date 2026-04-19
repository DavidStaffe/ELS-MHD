"""Demo incident seeder - creates full-featured demo with patients, transports,
resources (assigned to abschnitte), 6 beds (4 occupied), and messages."""
from datetime import datetime, timedelta
import logging
import random
import uuid

from core.db import db
from core.time import iso, now_utc
from models import Incident
from services.seeds import (
    seed_default_resources,
    update_resource_status_by_name,
)

logger = logging.getLogger(__name__)


async def create_demo_incident() -> dict:
    orte = [
        "Festplatz Sued", "Stadtpark West", "Messehalle 3",
        "Marathon KM 21", "Stadion Ost-Kurve",
    ]
    typen = ["veranstaltung", "sanitaetsdienst", "uebung"]
    namen = [
        "Stadtfest 2026", "Marathon Muenchen", "Open-Air Festival",
        "MANV-Uebung Sued", "Grossveranstaltung Messe",
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
    await seed_default_resources(obj.id)
    await _seed_demo_data(obj.id, start)
    logger.info("Demo-Incident erstellt: %s (%s)", obj.name, obj.id)
    return {k: v for k, v in doc.items() if k != "_id"}


async def _seed_demo_data(incident_id: str, incident_start: datetime):
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
        await db.incidents.update_one(
            {"id": incident_id}, {"$inc": {"patient_counter": 1}}
        )
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
            "fallabschluss_typ": "rd_uebergabe" if status == "uebergeben"
                                 else ("entlassung" if status == "entlassen" else None),
            "created_at": iso(ankunft),
            "updated_at": iso(now),
            "sichtung_at": iso(sichtung_at),
            "behandlung_start_at": iso(behandlung_start_at),
            "transport_angefordert_at": iso(transport_at) if transport_at else None,
            "fallabschluss_at": iso(fallabschluss_at) if fallabschluss_at else None,
            "bett_id": None,
        }
        await db.patients.insert_one(patient_doc)

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
                "gestartet_at": iso(transport_at + timedelta(minutes=1))
                                 if t_status in ("unterwegs", "abgeschlossen") else None,
                "abgeschlossen_at": iso(fallabschluss_at)
                                     if t_status == "abgeschlossen" else None,
            }
            await db.transports.insert_one(transport_doc)
            if ressource and t_status != "abgeschlossen":
                await update_resource_status_by_name(incident_id, ressource, "im_einsatz")

    # Meldungen
    messages = [
        ("kritisch", "anforderung", "SAN 1",
         "Kollaps Haupteingang, zweiten Trupp alarmieren!", now - timedelta(minutes=9)),
        ("dringend", "lage", "UHS",
         "UHS Kapazitaet 80% erreicht", now - timedelta(minutes=15)),
        ("normal", "info", "EL",
         "Einsatz laeuft planmaessig", now - timedelta(minutes=30)),
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

    # Schritt 10: Einsatzabschnitte
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

    # Schritt 11: 6 Betten (4 belegt, 2 frei)
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

    active_patients = await db.patients.find(
        {"incident_id": incident_id,
         "status": {"$in": ["in_behandlung", "transportbereit"]}},
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
