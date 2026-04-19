"""
Step 07-09 Backend API Tests
- Step 08: Demo Incident (POST /api/incidents/demo) with 7 Patienten, 2 Transporte, Resources, Messages
- Step 09: Auswertung, Abschluss-Check, Report (14 Kapitel), Report-Versions, PATCH meta
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def demo_incident(api_client):
    """Create a demo incident via POST /api/incidents/demo"""
    r = api_client.post(f"{BASE_URL}/api/incidents/demo")
    assert r.status_code == 201, f"Failed to create demo incident: {r.status_code} {r.text}"
    inc = r.json()
    yield inc
    # Cleanup
    api_client.delete(f"{BASE_URL}/api/incidents/{inc['id']}")


# Step 08 - Demo Integration
class TestDemoIncident:
    def test_demo_incident_created(self, api_client, demo_incident):
        assert "id" in demo_incident
        assert demo_incident.get("demo") is True
        assert demo_incident.get("name")

    def test_demo_has_7_patients(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/patients")
        assert r.status_code == 200
        patients = r.json()
        assert len(patients) == 7, f"Expected 7 demo patients, got {len(patients)}"

    def test_demo_has_2_transports(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/transports")
        assert r.status_code == 200
        transports = r.json()
        assert len(transports) == 2, f"Expected 2 demo transports, got {len(transports)}"

    def test_demo_has_resources(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/resources")
        assert r.status_code == 200
        resources = r.json()
        assert len(resources) >= 9, f"Expected >=9 resources, got {len(resources)}"

    def test_demo_has_messages(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/messages")
        assert r.status_code == 200
        messages = r.json()
        assert len(messages) > 0, "Expected demo messages"


# Step 09 - Auswertung
class TestAuswertung:
    def test_auswertung_structure(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/auswertung")
        assert r.status_code == 200
        data = r.json()
        for key in ["A_patienten", "B_transporte", "C_kommunikation", "D_ressourcen", "E_konflikte", "F_metadaten"]:
            assert key in data, f"Missing block {key}"

    def test_auswertung_patient_counts(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/auswertung")
        data = r.json()
        a = data["A_patienten"]
        # Expect count and sichtung info
        assert a.get("gesamt", 0) == 7 or a.get("total", 0) == 7 or a.get("anzahl", 0) == 7 or any(
            v == 7 for k, v in a.items() if isinstance(v, int)
        ), f"Expected 7 patients somewhere: {a}"
        assert "sichtung" in a

    def test_auswertung_transporte(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/auswertung")
        data = r.json()
        b = data["B_transporte"]
        assert isinstance(b, dict)

    def test_auswertung_metadaten_has_einsatzdauer(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/auswertung")
        data = r.json()
        f = data["F_metadaten"]
        assert "einsatzdauer_min" in f


# Step 09 - Abschluss-Check
class TestAbschlussCheck:
    def test_abschluss_check_structure(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/abschluss-check")
        assert r.status_code == 200
        data = r.json()
        assert "bereit_fuer_abschluss" in data
        assert "blockers" in data
        assert "warnings" in data
        assert isinstance(data["blockers"], list)
        assert isinstance(data["warnings"], list)

    def test_fresh_demo_not_ready_for_abschluss(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/abschluss-check")
        data = r.json()
        assert data["bereit_fuer_abschluss"] is False, \
            f"Fresh demo should have blockers, got bereit={data['bereit_fuer_abschluss']}, blockers={data['blockers']}"
        assert len(data["blockers"]) > 0


# Step 09 - Report (14 Kapitel)
class TestReport:
    def test_report_has_14_kapitel(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/report")
        assert r.status_code == 200
        data = r.json()
        assert "kapitel" in data
        assert len(data["kapitel"]) == 14, f"Expected 14 Kapitel, got {len(data['kapitel'])}"

    def test_report_kapitel_titel(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/report")
        kap = r.json()["kapitel"]
        expected = [
            "Einsatzgrunddaten",
            "Organisation & Rollen",
            "Patientenuebersicht",
            "Patientenliste",
            "Sichtungsverteilung",
            "Behandlungszeiten",
            "Transporte",
            "Ressourcen",
            "Kommunikation",
            "Konflikte & Blocker",
            "Besondere Vorkommnisse",
            "Nachbearbeitung & Anmerkungen",
            "Freigabe",
            "Anhaenge & Quellen",
        ]
        for i, title in enumerate(expected):
            assert kap[i]["nr"] == i + 1
            assert kap[i]["titel"] == title, f"Kapitel {i+1}: expected '{title}', got '{kap[i]['titel']}'"


# Step 09 - Report Versions
class TestReportVersions:
    def test_create_version_and_freigabe_metadata(self, api_client, demo_incident):
        # Create version
        r = api_client.post(
            f"{BASE_URL}/api/incidents/{demo_incident['id']}/report-versions",
            json={"freigegeben_von": "TestLeiter", "kommentar": "Test Freigabe"}
        )
        assert r.status_code == 201, f"Create version failed: {r.text}"
        v = r.json()
        assert v["version"] == 1
        assert v["freigegeben_von"] == "TestLeiter"
        assert "snapshot" in v

        # Verify incident meta was updated
        inc = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}").json()
        meta = inc.get("meta") or {}
        assert meta.get("freigegeben_von") == "TestLeiter"
        assert meta.get("freigabe_at") is not None

    def test_list_versions(self, api_client, demo_incident):
        r = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}/report-versions")
        assert r.status_code == 200
        versions = r.json()
        assert len(versions) >= 1
        assert versions[0]["incident_id"] == demo_incident["id"]

    def test_create_second_version_increments(self, api_client, demo_incident):
        r = api_client.post(
            f"{BASE_URL}/api/incidents/{demo_incident['id']}/report-versions",
            json={"freigegeben_von": "TestLeiter2"}
        )
        assert r.status_code == 201
        v = r.json()
        assert v["version"] == 2


# Step 09 - PATCH meta
class TestPatchMeta:
    def test_patch_meta_besondere_and_nachbearbeitung(self, api_client, demo_incident):
        payload = {
            "besondere_vorkommnisse": "TEST_Keine besonderen Vorkommnisse",
            "nachbearbeitung": "TEST_Nachbesprechung am Montag 10 Uhr",
        }
        r = api_client.patch(f"{BASE_URL}/api/incidents/{demo_incident['id']}/meta", json=payload)
        assert r.status_code == 200
        inc = r.json()
        meta = inc.get("meta") or {}
        assert meta.get("besondere_vorkommnisse") == payload["besondere_vorkommnisse"]
        assert meta.get("nachbearbeitung") == payload["nachbearbeitung"]

        # Verify persistence via GET
        r2 = api_client.get(f"{BASE_URL}/api/incidents/{demo_incident['id']}")
        meta2 = (r2.json() or {}).get("meta") or {}
        assert meta2.get("besondere_vorkommnisse") == payload["besondere_vorkommnisse"]
        assert meta2.get("nachbearbeitung") == payload["nachbearbeitung"]


# 404 tests
class TestNotFound:
    def test_auswertung_404(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/incidents/nonexistent-xyz/auswertung")
        assert r.status_code == 404

    def test_report_404(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/incidents/nonexistent-xyz/report")
        assert r.status_code == 404

    def test_abschluss_check_404(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/incidents/nonexistent-xyz/abschluss-check")
        assert r.status_code == 404

    def test_patch_meta_404(self, api_client):
        r = api_client.patch(
            f"{BASE_URL}/api/incidents/nonexistent-xyz/meta",
            json={"besondere_vorkommnisse": "x"}
        )
        assert r.status_code == 404
