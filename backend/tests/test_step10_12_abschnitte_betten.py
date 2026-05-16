"""
Tests for Schritte 10 (Einsatzabschnitte), 11 (Betten/UHS) und 12 (Integration).

Covers:
- CRUD for Abschnitte and Betten
- Bulk-creation, assign/release flows
- Demo-Seed shape (2 Abschnitte, 6 Betten, 4 belegt)
- Auswertung: Block G_abschnitte (Ampel), A_patienten.betten KPIs
- Abschluss-Check: new blockers/warnings
- Report (chapter 2 + chapter 8) includes abschnitte/betten info
- Regression: 14 report chapters, incident demo seeding
"""

import os
import pytest
import requests
from pathlib import Path


def _load_frontend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if url:
        return url.rstrip("/")
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    return ""


BASE_URL = _load_frontend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def demo_incident():
    """Create a demo incident once per module and clean up afterwards."""
    r = requests.post(f"{API}/incidents/demo", timeout=30)
    assert r.status_code in (200, 201), f"demo create failed {r.status_code}: {r.text}"
    inc = r.json()
    inc_id = inc["id"]
    yield inc
    # teardown
    try:
        requests.delete(f"{API}/incidents/{inc_id}", timeout=15)
    except Exception:
        pass


@pytest.fixture(scope="module")
def empty_incident():
    """Separate plain incident for isolated CRUD tests."""
    r = requests.post(
        f"{API}/incidents",
        json={"name": "TEST_Abschnitt_Bett", "typ": "uebung", "ort": "Testhalle"},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    inc = r.json()
    yield inc
    try:
        requests.delete(f"{API}/incidents/{inc['id']}", timeout=15)
    except Exception:
        pass


# ---------- Demo-Seed ----------

class TestDemoSeed:
    def test_demo_has_two_abschnitte(self, demo_incident):
        inc_id = demo_incident["id"]
        r = requests.get(f"{API}/incidents/{inc_id}/abschnitte", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2, f"expected 2, got {len(data)}"
        names = sorted([a["name"] for a in data])
        assert names == ["Abschnitt Nord", "BHP / UHS"], names
        for a in data:
            assert a["incident_id"] == inc_id
            assert a.get("farbe")
            assert a.get("aktiv") is True

    def test_demo_resources_assigned_to_abschnitte(self, demo_incident):
        inc_id = demo_incident["id"]
        rr = requests.get(f"{API}/incidents/{inc_id}/resources", timeout=10)
        assert rr.status_code == 200
        ress = rr.json()
        assigned = [r for r in ress if r.get("abschnitt_id")]
        assert len(assigned) >= 1, "at least some demo resources should be assigned"

    def test_demo_has_six_betten_four_belegt(self, demo_incident):
        inc_id = demo_incident["id"]
        r = requests.get(f"{API}/incidents/{inc_id}/betten", timeout=10)
        assert r.status_code == 200
        betten = r.json()
        assert len(betten) == 6, f"expected 6 betten, got {len(betten)}"
        belegt = [b for b in betten if b.get("status") == "belegt"]
        frei = [b for b in betten if b.get("status") == "frei"]
        assert len(belegt) == 4, f"expected 4 belegt, got {len(belegt)}"
        assert len(frei) == 2, f"expected 2 frei, got {len(frei)}"
        for b in belegt:
            assert b.get("patient_id"), "belegtes Bett muss patient_id haben"
            assert b.get("belegt_seit"), "belegtes Bett muss belegt_seit haben"


# ---------- Abschnitt CRUD ----------

class TestAbschnittCRUD:
    def test_create_get_update_list(self, empty_incident):
        inc_id = empty_incident["id"]
        # CREATE
        r = requests.post(
            f"{API}/incidents/{inc_id}/abschnitte",
            json={"name": "TEST_Abschnitt A", "farbe": "red"},
            timeout=10,
        )
        assert r.status_code == 201, r.text
        a = r.json()
        assert a["name"] == "TEST_Abschnitt A"
        assert a["farbe"] == "red"
        assert a["aktiv"] is True
        aid = a["id"]

        # GET single
        g = requests.get(f"{API}/abschnitte/{aid}", timeout=10)
        assert g.status_code == 200
        assert g.json()["id"] == aid

        # LIST
        lst = requests.get(f"{API}/incidents/{inc_id}/abschnitte", timeout=10)
        assert lst.status_code == 200
        assert any(x["id"] == aid for x in lst.json())

        # PATCH toggle aktiv false
        p = requests.patch(f"{API}/abschnitte/{aid}", json={"aktiv": False}, timeout=10)
        assert p.status_code == 200
        assert p.json()["aktiv"] is False

    def test_delete_active_incident_returns_204(self, empty_incident):
        """Aktive/operative Incidents: leerer Abschnitt darf geloescht werden (neue Regel).

        Inkidente Status spielt keine Rolle mehr; entscheidend ist nur, ob Betten belegt sind.
        """
        inc_id = empty_incident["id"]
        r = requests.post(
            f"{API}/incidents/{inc_id}/abschnitte",
            json={"name": "TEST_ZuLoeschen", "farbe": "blue"},
            timeout=10,
        )
        assert r.status_code == 201
        aid = r.json()["id"]
        d = requests.delete(f"{API}/abschnitte/{aid}", timeout=10)
        assert d.status_code == 204, f"expected 204, got {d.status_code}: {d.text}"

    def test_delete_after_incident_abgeschlossen(self):
        """Bei status!=aktiv darf Abschnitt geloescht werden."""
        r = requests.post(
            f"{API}/incidents",
            json={"name": "TEST_DeleteableAbschnitt", "typ": "uebung"},
            timeout=10,
        )
        inc_id = r.json()["id"]
        # create abschnitt
        ar = requests.post(
            f"{API}/incidents/{inc_id}/abschnitte",
            json={"name": "TEST_Weg"},
            timeout=10,
        )
        aid = ar.json()["id"]
        # close incident
        u = requests.patch(f"{API}/incidents/{inc_id}", json={"status": "abgeschlossen"}, timeout=10)
        assert u.status_code in (200, 204)
        # delete abschnitt -> 204
        d = requests.delete(f"{API}/abschnitte/{aid}", timeout=10)
        assert d.status_code == 204, d.text
        # cleanup
        requests.delete(f"{API}/incidents/{inc_id}", timeout=10)


# ---------- Bett CRUD + Bulk + Assign/Release ----------

class TestBettCRUD:
    def test_crud_and_bulk(self, empty_incident):
        inc_id = empty_incident["id"]
        # single create
        r = requests.post(
            f"{API}/incidents/{inc_id}/betten",
            json={"name": "TEST_Bett1", "typ": "liegend"},
            timeout=10,
        )
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["status"] == "frei"
        assert b["typ"] == "liegend"
        bid = b["id"]

        # patch
        p = requests.patch(f"{API}/betten/{bid}", json={"typ": "sitzend"}, timeout=10)
        assert p.status_code == 200
        assert p.json()["typ"] == "sitzend"

        # bulk
        br = requests.post(
            f"{API}/incidents/{inc_id}/betten/bulk",
            json={"anzahl": 3, "typ": "liegend", "praefix": "TEST_Bulk", "start_index": 10},
            timeout=15,
        )
        assert br.status_code == 201
        created = br.json()
        assert len(created) == 3
        names = [c["name"] for c in created]
        assert names == ["TEST_Bulk 10", "TEST_Bulk 11", "TEST_Bulk 12"]

        # delete single (frei) -> 204
        d = requests.delete(f"{API}/betten/{bid}", timeout=10)
        assert d.status_code == 204

    def test_assign_release_flow(self, empty_incident):
        inc_id = empty_incident["id"]
        # create Patient
        pr = requests.post(
            f"{API}/incidents/{inc_id}/patients",
            json={"kennung": "TEST_PAT_A", "sichtung": "S2", "status": "in_behandlung"},
            timeout=10,
        )
        assert pr.status_code in (200, 201), pr.text
        pid = pr.json()["id"]

        # create Bett
        br = requests.post(
            f"{API}/incidents/{inc_id}/betten",
            json={"name": "TEST_Assign"},
            timeout=10,
        )
        bid = br.json()["id"]

        # assign
        ar = requests.post(f"{API}/betten/{bid}/assign", json={"patient_id": pid}, timeout=10)
        assert ar.status_code == 200, ar.text
        assert ar.json()["status"] == "belegt"
        assert ar.json()["patient_id"] == pid
        assert ar.json()["belegt_seit"] is not None

        # patient has bett_id
        gp = requests.get(f"{API}/patients/{pid}", timeout=10)
        assert gp.json().get("bett_id") == bid

        # cannot delete belegtes Bett
        dd = requests.delete(f"{API}/betten/{bid}", timeout=10)
        assert dd.status_code == 409, dd.text

        # release
        rr = requests.post(f"{API}/betten/{bid}/release", timeout=10)
        assert rr.status_code == 200
        assert rr.json()["status"] == "frei"
        assert rr.json()["patient_id"] is None

        # patient bett_id removed
        gp2 = requests.get(f"{API}/patients/{pid}", timeout=10)
        assert gp2.json().get("bett_id") in (None, "")

    def test_gesperrt_cannot_be_assigned(self, empty_incident):
        inc_id = empty_incident["id"]
        # create patient
        pr = requests.post(
            f"{API}/incidents/{inc_id}/patients",
            json={"kennung": "TEST_PAT_B", "sichtung": "S2", "status": "in_behandlung"},
            timeout=10,
        )
        pid = pr.json()["id"]
        # create gesperrt bett
        br = requests.post(
            f"{API}/incidents/{inc_id}/betten",
            json={"name": "TEST_Gesperrt", "status": "gesperrt"},
            timeout=10,
        )
        bid = br.json()["id"]
        # assign -> 409
        ar = requests.post(f"{API}/betten/{bid}/assign", json={"patient_id": pid}, timeout=10)
        assert ar.status_code == 409, ar.text

    def test_patient_fallabschluss_releases_bett(self, empty_incident):
        inc_id = empty_incident["id"]
        pr = requests.post(
            f"{API}/incidents/{inc_id}/patients",
            json={"kennung": "TEST_PAT_C", "sichtung": "S2", "status": "in_behandlung"},
            timeout=10,
        )
        pid = pr.json()["id"]
        br = requests.post(
            f"{API}/incidents/{inc_id}/betten",
            json={"name": "TEST_AutoRelease"},
            timeout=10,
        )
        bid = br.json()["id"]
        ar = requests.post(f"{API}/betten/{bid}/assign", json={"patient_id": pid}, timeout=10)
        assert ar.status_code == 200

        # Fall abschliessen via status=entlassen
        up = requests.patch(
            f"{API}/patients/{pid}",
            json={"status": "entlassen"},
            timeout=10,
        )
        assert up.status_code == 200, up.text

        # Bett freigegeben?
        gb = requests.get(f"{API}/betten/{bid}", timeout=10)
        assert gb.status_code == 200
        assert gb.json()["status"] == "frei"
        assert gb.json().get("patient_id") in (None, "")


# ---------- Auswertung & Abschluss-Check & Report ----------

class TestIntegrationSchritt12:
    def test_auswertung_block_g_and_betten(self, demo_incident):
        inc_id = demo_incident["id"]
        r = requests.get(f"{API}/incidents/{inc_id}/auswertung", timeout=15)
        assert r.status_code == 200
        data = r.json()
        # Block G
        assert "G_abschnitte" in data
        g = data["G_abschnitte"]
        assert g["total"] == 2
        assert g["aktiv"] == 2
        assert len(g["abschnitte"]) == 2
        for item in g["abschnitte"]:
            assert item["ampel"] in ("red", "yellow", "green", "gray")
            assert "ressourcen_total" in item
            assert "betten_total" in item
        # Block A betten
        betten_kpi = data["A_patienten"]["betten"]
        assert betten_kpi["total"] == 6
        assert betten_kpi["belegt"] == 4
        assert betten_kpi["frei"] == 2
        assert "auslastung_pct" in betten_kpi
        assert "belegungsdauer_min_avg" in betten_kpi
        assert "max_gleichzeitig" in betten_kpi
        # Auslastung 4/6 ~66.7%
        assert 60.0 <= betten_kpi["auslastung_pct"] <= 70.0

    def test_abschluss_check_has_active_patient_blocker(self, demo_incident):
        inc_id = demo_incident["id"]
        r = requests.get(f"{API}/incidents/{inc_id}/abschluss-check", timeout=15)
        assert r.status_code == 200
        data = r.json()
        # Demo erzeugt offene Patienten/Transporte -> blocker exist
        blockers_ids = {b["id"] for b in data["blockers"]}
        # offene_patienten should exist, abschluss should be False
        assert data["bereit_fuer_abschluss"] is False
        assert "offene_patienten" in blockers_ids or "offene_transporte" in blockers_ids

    def test_abschluss_check_aktive_ohne_bett_blocker(self, empty_incident):
        """Erstelle Patient in_behandlung ohne Bett und ohne Transport -> blocker."""
        inc_id = empty_incident["id"]
        # Patient in_behandlung ohne bett/transport
        pr = requests.post(
            f"{API}/incidents/{inc_id}/patients",
            json={"kennung": "TEST_OHNE_BETT", "sichtung": "S2", "status": "in_behandlung"},
            timeout=10,
        )
        assert pr.status_code in (200, 201)
        r = requests.get(f"{API}/incidents/{inc_id}/abschluss-check", timeout=15)
        assert r.status_code == 200
        ids = {b["id"] for b in r.json()["blockers"]}
        assert "aktive_ohne_bett_transport" in ids

    def test_report_chapters_include_abschnitte_betten(self, demo_incident):
        inc_id = demo_incident["id"]
        r = requests.get(f"{API}/incidents/{inc_id}/report", timeout=20)
        assert r.status_code == 200
        data = r.json()
        kapitel = data.get("kapitel", [])
        assert len(kapitel) == 14, f"expected 14 kapitel, got {len(kapitel)}"
        # Chapter 2 should include abschnitte
        k2 = kapitel[1]
        body_str = str(k2)
        assert "abschnitt" in body_str.lower() or "Abschnitt" in body_str
        # Chapter 8
        k8 = kapitel[7]
        body8 = str(k8).lower()
        assert "bett" in body8 or "abschnitt" in body8


# ---------- Regression: Demo baseline ----------

class TestRegression:
    def test_demo_patients_transports_exist(self, demo_incident):
        inc_id = demo_incident["id"]
        p = requests.get(f"{API}/incidents/{inc_id}/patients", timeout=10)
        assert p.status_code == 200
        assert len(p.json()) >= 5
        t = requests.get(f"{API}/incidents/{inc_id}/transports", timeout=10)
        assert t.status_code == 200
        assert len(t.json()) >= 1
