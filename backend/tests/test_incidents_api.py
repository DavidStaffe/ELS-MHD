"""
Backend API Tests for ELS MHD - Incident Management (Step 02)
Tests: /api/meta, /api/incidents CRUD, demo incident, filtering
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


class TestMetaEndpoint:
    """Tests for /api/meta endpoint"""

    def test_meta_returns_version_0_2_0(self, api_client):
        """GET /api/meta should return version 0.2.0 and step info"""
        response = api_client.get(f"{BASE_URL}/api/meta")
        assert response.status_code == 200

        data = response.json()
        assert (
            data["version"] == "0.2.0"
        ), f"Expected version 0.2.0, got {data.get('version')}"
        assert "step" in data, "Response should contain 'step' field"
        assert "02" in data["step"], f"Step should contain '02', got {data.get('step')}"
        assert data["app"] == "ELS MHD"


class TestIncidentsListAndFilter:
    """Tests for GET /api/incidents with filtering"""

    def test_list_incidents_returns_array(self, api_client):
        """GET /api/incidents should return an array"""
        response = api_client.get(f"{BASE_URL}/api/incidents")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_filter_by_status_operativ(self, api_client):
        """GET /api/incidents?status=operativ should filter correctly"""
        response = api_client.get(
            f"{BASE_URL}/api/incidents", params={"status": "operativ"}
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        for incident in data:
            assert (
                incident["status"] == "operativ"
            ), f"Expected status 'operativ', got {incident.get('status')}"

    def test_filter_by_demo_true(self, api_client):
        """GET /api/incidents?demo=true should filter correctly"""
        response = api_client.get(f"{BASE_URL}/api/incidents", params={"demo": "true"})
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        for incident in data:
            assert (
                incident["demo"] == True
            ), f"Expected demo=true, got {incident.get('demo')}"


class TestDemoIncidentCreation:
    """Tests for POST /api/incidents/demo"""

    def test_create_demo_incident(self, api_client):
        """POST /api/incidents/demo should create a demo incident"""
        response = api_client.post(f"{BASE_URL}/api/incidents/demo")
        assert response.status_code == 201

        data = response.json()
        # Verify demo flag
        assert data["demo"] == True, f"Expected demo=true, got {data.get('demo')}"
        # Verify status is operativ
        assert (
            data["status"] == "operativ"
        ), f"Expected status 'operativ', got {data.get('status')}"
        # Verify id is present and valid UUID format
        assert "id" in data, "Response should contain 'id'"
        assert len(data["id"]) > 0, "ID should not be empty"
        # Verify start_at is set
        assert "start_at" in data, "Response should contain 'start_at'"
        assert data["start_at"] is not None, "start_at should not be None"
        # Verify created_at is set
        assert "created_at" in data, "Response should contain 'created_at'"

        # Store for cleanup
        return data["id"]


class TestIncidentCRUD:
    """Tests for Incident CRUD operations"""

    @pytest.fixture
    def test_incident_id(self, api_client):
        """Create a test incident and return its ID, cleanup after test"""
        payload = {
            "name": "TEST_Pytest_Incident",
            "typ": "veranstaltung",
            "ort": "Test Location",
            "beschreibung": "Test description for pytest",
            "status": "operativ",
            "demo": False,
        }
        response = api_client.post(f"{BASE_URL}/api/incidents", json=payload)
        assert response.status_code == 201
        incident_id = response.json()["id"]
        yield incident_id
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/incidents/{incident_id}")

    def test_create_incident_with_valid_payload(self, api_client):
        """POST /api/incidents with valid payload should create non-demo incident"""
        payload = {
            "name": "TEST_Valid_Incident",
            "typ": "sanitaetsdienst",
            "ort": "Testplatz",
            "beschreibung": "Valid test incident",
            "status": "operativ",
            "demo": False,
        }
        response = api_client.post(f"{BASE_URL}/api/incidents", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == payload["name"]
        assert data["typ"] == payload["typ"]
        assert data["demo"] == False, "Non-demo incident should have demo=false"
        assert (
            "start_at" in data and data["start_at"] is not None
        ), "start_at should be set"
        assert "id" in data

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/incidents/{data['id']}")

    def test_create_incident_with_planned_status(self, api_client):
        """POST /api/incidents should allow planned incidents."""
        payload = {
            "name": "TEST_Planned_Incident",
            "typ": "einsatz",
            "status": "geplant",
            "demo": False,
        }
        response = api_client.post(f"{BASE_URL}/api/incidents", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["status"] == "geplant"
        assert data.get("start_at") is None

        api_client.delete(f"{BASE_URL}/api/incidents/{data['id']}")

    def test_planned_to_operativ_sets_start_at(self, api_client):
        """PATCH planned -> operativ should set start_at when it was not started yet."""
        create_resp = api_client.post(
            f"{BASE_URL}/api/incidents",
            json={
                "name": "TEST_Planned_To_Operativ_Start",
                "typ": "einsatz",
                "status": "geplant",
                "demo": False,
            },
        )
        assert create_resp.status_code == 201
        incident = create_resp.json()
        assert incident.get("start_at") is None

        patch_resp = api_client.patch(
            f"{BASE_URL}/api/incidents/{incident['id']}",
            json={"status": "operativ"},
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["status"] == "operativ"
        assert updated.get("start_at") is not None

        api_client.delete(f"{BASE_URL}/api/incidents/{incident['id']}")

    def test_create_incident_with_invalid_name_too_short(self, api_client):
        """POST /api/incidents with name too short should return 422"""
        payload = {"name": "X", "typ": "veranstaltung"}  # Too short (min 2 chars)
        response = api_client.post(f"{BASE_URL}/api/incidents", json=payload)
        assert (
            response.status_code == 422
        ), f"Expected 422 for invalid payload, got {response.status_code}"

    def test_get_incident_by_id_existing(self, api_client, test_incident_id):
        """GET /api/incidents/{id} should return 200 for existing incident"""
        response = api_client.get(f"{BASE_URL}/api/incidents/{test_incident_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == test_incident_id

    def test_get_incident_by_id_not_found(self, api_client):
        """GET /api/incidents/{id} should return 404 for unknown id"""
        fake_id = str(uuid.uuid4())
        response = api_client.get(f"{BASE_URL}/api/incidents/{fake_id}")
        assert response.status_code == 404

    def test_patch_incident_status_abgeschlossen_sets_end_at(
        self, api_client, test_incident_id
    ):
        """PATCH /api/incidents/{id} with status=abgeschlossen should set end_at automatically"""
        payload = {"status": "abgeschlossen"}
        response = api_client.patch(
            f"{BASE_URL}/api/incidents/{test_incident_id}", json=payload
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "abgeschlossen"
        assert "end_at" in data, "end_at should be present after closing"
        assert (
            data["end_at"] is not None
        ), "end_at should be set when status is abgeschlossen"

    def test_delete_incident_returns_204(self, api_client):
        """DELETE /api/incidents/{id} should return 204 and remove the entry"""
        # First create an incident to delete
        payload = {"name": "TEST_To_Delete", "typ": "uebung", "demo": True}
        create_response = api_client.post(f"{BASE_URL}/api/incidents", json=payload)
        assert create_response.status_code == 201
        incident_id = create_response.json()["id"]

        # Delete it
        delete_response = api_client.delete(f"{BASE_URL}/api/incidents/{incident_id}")
        assert delete_response.status_code == 204

        # Verify it's gone
        get_response = api_client.get(f"{BASE_URL}/api/incidents/{incident_id}")
        assert get_response.status_code == 404, "Deleted incident should return 404"

    def test_delete_incident_not_found(self, api_client):
        """DELETE /api/incidents/{id} should return 404 for unknown id"""
        fake_id = str(uuid.uuid4())
        response = api_client.delete(f"{BASE_URL}/api/incidents/{fake_id}")
        assert response.status_code == 404


class TestIncidentUpdate:
    """Additional update tests"""

    def test_update_incident_name(self, api_client):
        """PATCH /api/incidents/{id} should update name"""
        # Create
        payload = {"name": "TEST_Update_Name", "typ": "einsatz"}
        create_resp = api_client.post(f"{BASE_URL}/api/incidents", json=payload)
        assert create_resp.status_code == 201
        incident_id = create_resp.json()["id"]

        # Update
        update_payload = {"name": "TEST_Updated_Name"}
        update_resp = api_client.patch(
            f"{BASE_URL}/api/incidents/{incident_id}", json=update_payload
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "TEST_Updated_Name"

        # Verify via GET
        get_resp = api_client.get(f"{BASE_URL}/api/incidents/{incident_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "TEST_Updated_Name"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/incidents/{incident_id}")
