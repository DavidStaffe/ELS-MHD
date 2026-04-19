"""Shared Literal types for all ELS-MHD domains."""
from typing import Literal

IncidentTyp = Literal[
    "veranstaltung",
    "sanitaetsdienst",
    "uebung",
    "einsatz",
    "sonstiges",
]
IncidentStatus = Literal["geplant", "operativ", "abgeschlossen", "archiviert"]

SichtungStufe = Literal["S0", "S1", "S2", "S3"]
PatientStatus = Literal[
    "wartend",
    "in_behandlung",
    "transportbereit",
    "uebergeben",
    "entlassen",
]
PatientVerbleib = Literal[
    "unbekannt", "uhs", "rd", "krankenhaus", "event", "heim", "sonstiges"
]

TransportTyp = Literal["intern", "extern"]
FallabschlussTyp = Literal["rd_uebergabe", "entlassung", "manuell"]
TransportZiel = Literal[
    "uhs", "krankenhaus", "rd", "event", "heim", "sonstiges"
]
TransportStatus = Literal["offen", "zugewiesen", "unterwegs", "abgeschlossen"]

ResourceKategorie = Literal["uhs", "rtw", "ktw", "nef", "evt", "sonstiges"]
ResourceStatus = Literal["verfuegbar", "im_einsatz", "wartung", "offline"]

MessagePrio = Literal["kritisch", "dringend", "normal"]
MessageKat = Literal["info", "lage", "anforderung", "warnung"]

# Schritt 13: Funktagebuch-Eintragstypen
FunkTyp = Literal[
    "funk_ein",       # Funkmeldung eingehend
    "funk_aus",       # Funkmeldung ausgehend
    "lage",           # Lagemeldung
    "auftrag",        # Auftrag / Weisung
    "rueckmeldung",   # Rueckmeldung / Statusmeldung
    "vorkommnis",     # Besonderes Vorkommnis
    "system",         # Automatischer Systemeintrag
]
FunkQuelle = Literal["manuell", "system"]

BettTyp = Literal["liegend", "sitzend", "schockraum", "beobachtung", "sonstiges"]
BettStatus = Literal["frei", "belegt", "gesperrt"]
