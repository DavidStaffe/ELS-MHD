"""Step 13: Funktagebuch + Ressourcen-CRUD regression tests."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def incident_id():
    """Creates a fresh test incident, cleans up at end."""
    r = requests.post(f"{API}/incidents", json={
        "name": f"TEST_Funk_{uuid.uuid4().hex[:6]}",
        "typ": "veranstaltung",
        "ort": "Test",
        "status": "operativ",
    })
    assert r.status_code in (200, 201), r.text
    iid = r.json()["id"]
    yield iid
    # cleanup
    requests.delete(f"{API}/incidents/{iid}")


@pytest.fixture(scope="module")
def demo_incident_id():
    r = requests.post(f"{API}/incidents/demo")
    assert r.status_code in (200, 201)
    return r.json()["id"]


# --- 1) CRUD with new fields -------------------------------------------------

def test_create_message_with_new_fields(incident_id):
    payload = {
        "text": "Lagemeldung Abschnitt Nord",
        "prioritaet": "dringend",
        "funk_typ": "lage",
        "absender": "EL",
        "empfaenger": "FA",
        "erfasst_von": "Max",
        "erfasst_rolle": "einsatzleiter",
    }
    r = requests.post(f"{API}/incidents/{incident_id}/messages", json=payload)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["funk_typ"] == "lage"
    assert d["absender"] == "EL"
    assert d["empfaenger"] == "FA"
    assert d["quelle"] == "manuell"
    assert d["finalisiert"] is False
    assert d["erfasst_rolle"] == "einsatzleiter"


def test_list_messages_filters(incident_id):
    # seed three with varying types/prio
    for typ, prio in [("funk_ein", "normal"), ("auftrag", "kritisch"), ("rueckmeldung", "normal")]:
        requests.post(f"{API}/incidents/{incident_id}/messages", json={
            "text": f"t {typ}", "funk_typ": typ, "prioritaet": prio,
            "absender": "X", "empfaenger": "Y",
        })
    r = requests.get(f"{API}/incidents/{incident_id}/messages",
                     params={"funk_typ": "funk_ein,auftrag"})
    assert r.status_code == 200
    items = r.json()
    assert all(m["funk_typ"] in ("funk_ein", "auftrag") for m in items)
    assert len(items) >= 2

    r = requests.get(f"{API}/incidents/{incident_id}/messages",
                     params={"prioritaet": "kritisch"})
    assert all(m["prioritaet"] == "kritisch" for m in r.json())

    r = requests.get(f"{API}/incidents/{incident_id}/messages",
                     params={"quelle": "manuell"})
    assert all(m["quelle"] == "manuell" for m in r.json())

    r = requests.get(f"{API}/incidents/{incident_id}/messages", params={"q": "Lagemeldung"})
    assert any("Lagemeldung" in m["text"] for m in r.json())


def test_confirm_message(incident_id):
    r = requests.post(f"{API}/incidents/{incident_id}/messages", json={
        "text": "Lagemeldung conf", "funk_typ": "lage",
        "absender": "A", "empfaenger": "B",
    })
    mid = r.json()["id"]
    r2 = requests.post(f"{API}/messages/{mid}/confirm", json={"bestaetigt_von": "EL1"})
    assert r2.status_code == 200
    d = r2.json()
    assert d["bestaetigt_von"] == "EL1"
    assert d["bestaetigt_at"] is not None


def test_finalize_and_lock(incident_id):
    r = requests.post(f"{API}/incidents/{incident_id}/messages", json={
        "text": "final test", "funk_typ": "lage",
        "absender": "A", "empfaenger": "B",
    })
    mid = r.json()["id"]
    r2 = requests.post(f"{API}/messages/{mid}/finalize", params={"by": "EL"})
    assert r2.status_code == 200
    d = r2.json()
    assert d["finalisiert"] is True
    assert d["finalisiert_at"] is not None

    # PATCH on finalized -> 409
    r3 = requests.patch(f"{API}/messages/{mid}", json={"text": "change"})
    assert r3.status_code == 409

    # DELETE on finalized -> 409
    r4 = requests.delete(f"{API}/messages/{mid}")
    assert r4.status_code == 409


def test_patient_creation_creates_system_entry(incident_id):
    r = requests.post(f"{API}/incidents/{incident_id}/patients", json={
        "sichtung": "S2", "status": "wartend", "notiz": "TESTPat",
    })
    assert r.status_code == 201, r.text
    pat = r.json()

    msgs = requests.get(f"{API}/incidents/{incident_id}/messages",
                        params={"quelle": "system"}).json()
    sys_for_pat = [m for m in msgs if m.get("patient_id") == pat["id"]]
    assert sys_for_pat, "No system entry for new patient"
    s = sys_for_pat[0]
    assert s["funk_typ"] == "system"
    assert s["quelle"] == "system"
    assert s["finalisiert"] is True
    assert pat["kennung"] in s["text"]
    assert "S2" in s["text"]

    # PATCH on system -> 409
    r2 = requests.patch(f"{API}/messages/{s['id']}", json={"text": "nope"})
    assert r2.status_code == 409
    # DELETE on system -> 409
    r3 = requests.delete(f"{API}/messages/{s['id']}")
    assert r3.status_code == 409


def test_patient_fallabschluss_logs_system_entry(incident_id):
    r = requests.post(f"{API}/incidents/{incident_id}/patients", json={"sichtung": "S1"})
    pid = r.json()["id"]
    r2 = requests.patch(f"{API}/patients/{pid}", json={"status": "uebergeben"})
    assert r2.status_code == 200

    msgs = requests.get(f"{API}/incidents/{incident_id}/messages",
                        params={"quelle": "system"}).json()
    for_pat = [m for m in msgs if m.get("patient_id") == pid]
    assert any("Fallabschluss" in m["text"] or "uebergeben" in m["text"].lower()
               or "abschluss" in m["text"].lower() for m in for_pat), \
        f"No fallabschluss system entry: {[m['text'] for m in for_pat]}"


def test_transport_status_change_logs_system_entry(incident_id):
    # create patient + transport
    p = requests.post(f"{API}/incidents/{incident_id}/patients", json={"sichtung": "S2"}).json()
    r = requests.post(f"{API}/incidents/{incident_id}/transports", json={
        "typ": "intern", "ziel": "uhs", "patient_id": p["id"],
    })
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    r2 = requests.patch(f"{API}/transports/{tid}", json={"status": "unterwegs"})
    assert r2.status_code == 200

    msgs = requests.get(f"{API}/incidents/{incident_id}/messages",
                        params={"quelle": "system", "funk_typ": "system"}).json()
    for_t = [m for m in msgs if m.get("transport_id") == tid]
    assert for_t, "no system entry for transport status"
    assert all(m["funk_typ"] == "system" for m in for_t)


def test_demo_seed_has_four_initial_funk_entries(demo_incident_id):
    msgs = requests.get(f"{API}/incidents/{demo_incident_id}/messages").json()
    # Filter for manual entries (excluding system-generated from demo patients/transports)
    manual = [m for m in msgs if m.get("quelle") == "manuell"]
    assert len(manual) >= 4, f"Expected >=4 manual demo messages, got {len(manual)}"
    types = {m.get("funk_typ") for m in manual}
    expected = {"funk_ein", "lage", "auftrag", "rueckmeldung"}
    assert expected.issubset(types), f"Missing types. Got: {types}"


# --- 2) Resources CRUD regression -------------------------------------------

def test_resource_crud(incident_id):
    r = requests.post(f"{API}/incidents/{incident_id}/resources", json={
        "name": "TEST_RTW1", "typ": "extern", "kategorie": "rtw", "status": "verfuegbar",
    })
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    r2 = requests.patch(f"{API}/resources/{rid}", json={"status": "im_einsatz"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "im_einsatz"

    r3 = requests.delete(f"{API}/resources/{rid}")
    assert r3.status_code in (200, 204)
