"""
Backend API Tests for ELS MHD - Patient Management (Step 03)
Tests: Patient CRUD, auto-kennung, timestamps, filtering, cascade delete
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def test_incident(api_client):
    """Create a test incident for patient tests, cleanup after all tests"""
    payload = {
        "name": "TEST_Patient_Incident",
        "typ": "uebung",
        "ort": "Test Location",
        "beschreibung": "Test incident for patient API tests",
        "status": "operativ",
        "demo": False,
    }
    response = api_client.post(f"{BASE_URL}/api/incidents", json=payload)
    assert (
        response.status_code == 201
    ), f"Failed to create test incident: {response.text}"
    incident = response.json()
    yield incident
    # Cleanup - delete incident (should cascade delete patients)
    api_client.delete(f"{BASE_URL}/api/incidents/{incident['id']}")


class TestPatientCreation:
    """Tests for POST /api/incidents/{id}/patients"""

    def test_create_patient_without_payload_defaults(self, api_client, test_incident):
        """POST without payload: creates Patient with status=wartend, kennung=P-XXXX"""
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={}
        )
        assert (
            response.status_code == 201
        ), f"Expected 201, got {response.status_code}: {response.text}"

        data = response.json()
        # Verify defaults
        assert (
            data["status"] == "wartend"
        ), f"Expected status 'wartend', got {data.get('status')}"
        assert data["kennung"].startswith(
            "P-"
        ), f"Kennung should start with P-, got {data.get('kennung')}"
        assert (
            len(data["kennung"]) == 6
        ), f"Kennung should be P-XXXX format, got {data.get('kennung')}"
        assert (
            data["sichtung"] is None
        ), f"Sichtung should be None by default, got {data.get('sichtung')}"
        assert (
            data["verbleib"] == "unbekannt"
        ), f"Verbleib should be 'unbekannt', got {data.get('verbleib')}"
        assert data["incident_id"] == test_incident["id"]
        assert "id" in data
        assert "created_at" in data

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{data['id']}")

    def test_create_patient_with_sichtung_s1(self, api_client, test_incident):
        """POST with sichtung=S1: creates Patient with sichtung=S1, status=in_behandlung, timestamps set"""
        payload = {"sichtung": "S1"}
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json=payload
        )
        assert response.status_code == 201

        data = response.json()
        assert (
            data["sichtung"] == "S1"
        ), f"Expected sichtung 'S1', got {data.get('sichtung')}"
        assert (
            data["status"] == "in_behandlung"
        ), f"Expected status 'in_behandlung' when sichtung set, got {data.get('status')}"
        assert (
            data["sichtung_at"] is not None
        ), "sichtung_at should be set when sichtung provided"
        assert (
            data["behandlung_start_at"] is None
        ), "behandlung_start_at should NOT be set until a resource is assigned"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{data['id']}")

    def test_create_patient_with_sichtung_s2(self, api_client, test_incident):
        """POST with sichtung=S2: creates Patient with sichtung=S2"""
        payload = {"sichtung": "S2"}
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json=payload
        )
        assert response.status_code == 201

        data = response.json()
        assert data["sichtung"] == "S2"
        assert data["status"] == "in_behandlung"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{data['id']}")

    def test_create_patient_with_sichtung_s3(self, api_client, test_incident):
        """POST with sichtung=S3: creates Patient with sichtung=S3"""
        payload = {"sichtung": "S3"}
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json=payload
        )
        assert response.status_code == 201

        data = response.json()
        assert data["sichtung"] == "S3"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{data['id']}")

    def test_create_patient_with_sichtung_s4(self, api_client, test_incident):
        """POST with sichtung=S4: creates Patient with sichtung=S4"""
        payload = {"sichtung": "S4"}
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json=payload
        )
        assert response.status_code == 201

        data = response.json()
        assert data["sichtung"] == "S4"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{data['id']}")

    def test_create_patient_invalid_sichtung_returns_422(
        self, api_client, test_incident
    ):
        """POST with invalid sichtung (e.g., 'SX') should return 422"""
        payload = {"sichtung": "SX"}
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json=payload
        )
        assert (
            response.status_code == 422
        ), f"Expected 422 for invalid sichtung, got {response.status_code}"

    def test_create_patient_invalid_incident_returns_404(self, api_client):
        """POST to non-existent incident should return 404"""
        fake_id = str(uuid.uuid4())
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{fake_id}/patients", json={}
        )
        assert response.status_code == 404


class TestPatientAutoKennung:
    """Tests for auto-generated kennung (P-0001, P-0002, ...)"""

    def test_auto_kennung_sequential(self, api_client, test_incident):
        """Auto-Kennung should be sequential per Incident (P-0001, P-0002, ...)"""
        # Create first patient
        resp1 = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={}
        )
        assert resp1.status_code == 201
        p1 = resp1.json()
        kennung1 = p1["kennung"]

        # Create second patient
        resp2 = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={}
        )
        assert resp2.status_code == 201
        p2 = resp2.json()
        kennung2 = p2["kennung"]

        # Extract numbers
        num1 = int(kennung1.split("-")[1])
        num2 = int(kennung2.split("-")[1])

        assert (
            num2 == num1 + 1
        ), f"Kennung should be sequential: {kennung1} -> {kennung2}"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p1['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{p2['id']}")


class TestPatientList:
    """Tests for GET /api/incidents/{id}/patients"""

    def test_list_patients_returns_array(self, api_client, test_incident):
        """GET /api/incidents/{id}/patients should return array for incident"""
        response = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients"
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_list_patients_filter_by_sichtung(self, api_client, test_incident):
        """GET with ?sichtung=S1,S2 should filter correctly"""
        # Create patients with different sichtung
        p1 = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S1"},
        ).json()
        p2 = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S2"},
        ).json()
        p3 = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S3"},
        ).json()

        # Filter by S1,S2
        response = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            params={"sichtung": "S1,S2"},
        )
        assert response.status_code == 200

        data = response.json()
        for patient in data:
            assert patient["sichtung"] in [
                "S1",
                "S2",
            ], f"Filter failed: got sichtung {patient.get('sichtung')}"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p1['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{p2['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{p3['id']}")

    def test_list_patients_filter_by_status(self, api_client, test_incident):
        """GET with ?status=in_behandlung should filter correctly"""
        # Create patient with sichtung (will have status=in_behandlung)
        p1 = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S2"},
        ).json()
        # Create patient without sichtung (will have status=wartend)
        p2 = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={}
        ).json()

        # Filter by in_behandlung
        response = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            params={"status": "in_behandlung"},
        )
        assert response.status_code == 200

        data = response.json()
        for patient in data:
            assert (
                patient["status"] == "in_behandlung"
            ), f"Filter failed: got status {patient.get('status')}"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p1['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{p2['id']}")

    def test_list_patients_invalid_incident_returns_404(self, api_client):
        """GET for non-existent incident should return 404"""
        fake_id = str(uuid.uuid4())
        response = api_client.get(f"{BASE_URL}/api/incidents/{fake_id}/patients")
        assert response.status_code == 404


class TestPatientUpdate:
    """Tests for PATCH /api/patients/{id}"""

    def test_update_status_transportbereit_sets_timestamp(
        self, api_client, test_incident
    ):
        """PATCH with status=transportbereit should set transport_angefordert_at"""
        # Create patient
        p = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S2"},
        ).json()
        assert p["transport_angefordert_at"] is None

        # Update to transportbereit
        response = api_client.patch(
            f"{BASE_URL}/api/patients/{p['id']}", json={"status": "transportbereit"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "transportbereit"
        assert (
            data["transport_angefordert_at"] is not None
        ), "transport_angefordert_at should be set"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")

    def test_update_status_entlassen_sets_fallabschluss(
        self, api_client, test_incident
    ):
        """PATCH with status=entlassen should set fallabschluss_at"""
        # Create patient
        p = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S3"},
        ).json()

        # Update to entlassen
        response = api_client.patch(
            f"{BASE_URL}/api/patients/{p['id']}", json={"status": "entlassen"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "entlassen"
        assert (
            data["fallabschluss_at"] is not None
        ), "fallabschluss_at should be set when entlassen"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")

    def test_update_status_uebergeben_sets_fallabschluss(
        self, api_client, test_incident
    ):
        """PATCH with status=uebergeben should set fallabschluss_at"""
        # Create patient
        p = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S1"},
        ).json()

        # Update to uebergeben
        response = api_client.patch(
            f"{BASE_URL}/api/patients/{p['id']}", json={"status": "uebergeben"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "uebergeben"
        assert (
            data["fallabschluss_at"] is not None
        ), "fallabschluss_at should be set when uebergeben"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")

    def test_update_sichtung_on_unsichtiert_patient_sets_timestamps(
        self, api_client, test_incident
    ):
        """PATCH with sichtung on previously unsichtiert patient should set sichtung_at + behandlung_start_at"""
        # Create patient without sichtung
        p = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={}
        ).json()
        assert p["sichtung"] is None
        assert p["sichtung_at"] is None
        assert p["behandlung_start_at"] is None

        # Update with sichtung
        response = api_client.patch(
            f"{BASE_URL}/api/patients/{p['id']}", json={"sichtung": "S2"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["sichtung"] == "S2"
        assert (
            data["sichtung_at"] is not None
        ), "sichtung_at should be set when sichtung added"
        assert (
            data["behandlung_start_at"] is not None
        ), "behandlung_start_at should be set when sichtung added"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")

    def test_update_patient_not_found(self, api_client):
        """PATCH for non-existent patient should return 404"""
        fake_id = str(uuid.uuid4())
        response = api_client.patch(
            f"{BASE_URL}/api/patients/{fake_id}", json={"status": "wartend"}
        )
        assert response.status_code == 404


class TestPatientDelete:
    """Tests for DELETE /api/patients/{id}"""

    def test_delete_patient_returns_204(self, api_client, test_incident):
        """DELETE /api/patients/{id} should return 204"""
        # Create patient
        p = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={}
        ).json()

        # Delete
        response = api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")
        assert response.status_code == 204

        # Verify deleted
        get_response = api_client.get(f"{BASE_URL}/api/patients/{p['id']}")
        assert get_response.status_code == 404

    def test_delete_patient_not_found(self, api_client):
        """DELETE for non-existent patient should return 404"""
        fake_id = str(uuid.uuid4())
        response = api_client.delete(f"{BASE_URL}/api/patients/{fake_id}")
        assert response.status_code == 404


class TestIncidentDeleteCascade:
    """Tests for cascade delete of patients when incident is deleted"""

    def test_delete_incident_removes_patients(self, api_client):
        """DELETE Incident should also remove all associated patients"""
        # Create incident
        inc_resp = api_client.post(
            f"{BASE_URL}/api/incidents",
            json={"name": "TEST_Cascade_Delete", "typ": "uebung"},
        )
        assert inc_resp.status_code == 201
        incident = inc_resp.json()

        # Create patients
        p1 = api_client.post(
            f"{BASE_URL}/api/incidents/{incident['id']}/patients",
            json={"sichtung": "S1"},
        ).json()
        p2 = api_client.post(
            f"{BASE_URL}/api/incidents/{incident['id']}/patients",
            json={"sichtung": "S2"},
        ).json()

        # Verify patients exist
        assert api_client.get(f"{BASE_URL}/api/patients/{p1['id']}").status_code == 200
        assert api_client.get(f"{BASE_URL}/api/patients/{p2['id']}").status_code == 200

        # Delete incident
        del_resp = api_client.delete(f"{BASE_URL}/api/incidents/{incident['id']}")
        assert del_resp.status_code == 204

        # Verify patients are also deleted
        assert (
            api_client.get(f"{BASE_URL}/api/patients/{p1['id']}").status_code == 404
        ), "Patient should be deleted with incident"
        assert (
            api_client.get(f"{BASE_URL}/api/patients/{p2['id']}").status_code == 404
        ), "Patient should be deleted with incident"


class TestPatientGet:
    """Tests for GET /api/patients/{id}"""

    def test_get_patient_by_id(self, api_client, test_incident):
        """GET /api/patients/{id} should return patient details"""
        # Create patient
        p = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S2", "notiz": "Test note"},
        ).json()

        # Get patient
        response = api_client.get(f"{BASE_URL}/api/patients/{p['id']}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == p["id"]
        assert data["kennung"] == p["kennung"]
        assert data["sichtung"] == "S2"
        assert data["notiz"] == "Test note"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")

    def test_get_patient_not_found(self, api_client):
        """GET for non-existent patient should return 404"""
        fake_id = str(uuid.uuid4())
        response = api_client.get(f"{BASE_URL}/api/patients/{fake_id}")
        assert response.status_code == 404
