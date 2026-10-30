"""Unit tests for the privacy-preserving DIVI protocol payloads.

Run with: cd backend && pytest tests/test_patient_protocol_validation.py
"""
from datetime import date, timedelta
import os

# The model-only tests do not connect to MongoDB, but core.db initializes a client.
os.environ.setdefault('MONGO_URL', 'mongodb://127.0.0.1:27017')
os.environ.setdefault('DB_NAME', 'els_protocol_unit_test')

import pytest
from pydantic import ValidationError

from routes.patient_protocol import (
    Anamnese,
    Massnahmen,
    ProtocolPatch,
    Stammdaten,
    Verlauf,
    Vitalwert,
)


def test_only_birth_date_and_sex_are_personal_master_fields():
    assert set(Stammdaten.model_fields) == {"geburtsdatum", "geschlecht"}
    value = Stammdaten(geburtsdatum="1984-01-03", geschlecht="weiblich")
    assert value.model_dump(mode="json")["geburtsdatum"] == "1984-01-03"
    with pytest.raises(ValidationError):
        Stammdaten(geburtsdatum="1984-01-03", patientenname="Max Mustermann")
    with pytest.raises(ValidationError):
        Stammdaten(krankenkasse="Beispielkasse")


def test_birthdate_cannot_be_in_future():
    with pytest.raises(ValidationError):
        Stammdaten(geburtsdatum=date.today() + timedelta(days=1))


def test_medical_sections_are_whitelisted():
    with pytest.raises(ValidationError):
        Anamnese(symptome="Atemnot", vorname="Verboten")
    with pytest.raises(ValidationError):
        ProtocolPatch(section="versicherung", data={"nummer": "123"}, expected_version=0)


def test_vitals_are_plausibility_checked_and_time_stamped():
    value = Vitalwert(zeit="12:34", spo2=94, puls=105, gcs=15)
    assert value.puls == 105
    with pytest.raises(ValidationError):
        Vitalwert(zeit="25:61", spo2=100)
    with pytest.raises(ValidationError):
        Vitalwert(zeit="12:34", spo2=120)
    with pytest.raises(ValidationError):
        Verlauf(werte=[{"zeit": "12:34"}] * 49)


def test_treatment_entries_are_bounded_and_nonempty():
    with pytest.raises(ValidationError):
        Massnahmen(eintraege=[{"zeit": "13:00", "beschreibung": ""}])
    value = Massnahmen(eintraege=[{
        "zeit": "13:00", "typ": "medikament", "beschreibung": "Beispiel",
        "dosis": "1 mg", "appl_weg": "i.v."
    }])
    assert value.eintraege[0].typ == "medikament"
