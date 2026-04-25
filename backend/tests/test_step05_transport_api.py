"""
Backend API Tests for ELS MHD - Step 05: Transportuebersicht
Tests: Transport CRUD, Auto-Create on patient.transport_typ, Auto-Complete on patient status,
       Cascade delete, filtering, status transitions with timestamps
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def test_incident(api_client):
    """Create a test incident for transport tests, cleanup after all tests"""
    payload = {
        "name": "TEST_Step05_Transport_Incident",
        "typ": "uebung",
        "ort": "Test Location",
        "beschreibung": "Test incident for Step 05 Transport API tests",
        "status": "operativ",
        "demo": False,
    }
    response = api_client.post(f"{BASE_URL}/api/incidents", json=payload)
    assert (
        response.status_code == 201
    ), f"Failed to create test incident: {response.text}"
    incident = response.json()
    yield incident
    # Cleanup - delete incident (should cascade delete patients and transports)
    api_client.delete(f"{BASE_URL}/api/incidents/{incident['id']}")


class TestMetaVersion:
    """Tests for GET /api/meta - version 0.5.0"""

    def test_meta_returns_version_050(self, api_client):
        """GET /api/meta should return version 0.5.0 and step '05 – Transportuebersicht'"""
        response = api_client.get(f"{BASE_URL}/api/meta")
        assert response.status_code == 200

        data = response.json()
        assert (
            data["version"] == "0.5.0"
        ), f"Expected version 0.5.0, got {data.get('version')}"
        assert (
            data["step"] == "05 – Transportuebersicht"
        ), f"Expected step '05 – Transportuebersicht', got {data.get('step')}"


class TestTransportListEndpoint:
    """Tests for GET /api/incidents/{id}/transports"""

    def test_list_transports_returns_array(self, api_client, test_incident):
        """GET /api/incidents/{id}/transports should return an array"""
        response = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports"
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_list_transports_nonexistent_incident_returns_404(self, api_client):
        """GET /api/incidents/{nonexistent}/transports should return 404"""
        response = api_client.get(f"{BASE_URL}/api/incidents/nonexistent-id/transports")
        assert response.status_code == 404


class TestTransportCreate:
    """Tests for POST /api/incidents/{id}/transports"""

    def test_create_transport_without_ressource_status_offen(
        self, api_client, test_incident
    ):
        """POST without ressource should create transport with status=offen"""
        payload = {"typ": "extern", "ziel": "krankenhaus"}
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports", json=payload
        )
        assert (
            response.status_code == 201
        ), f"Expected 201, got {response.status_code}: {response.text}"

        data = response.json()
        assert (
            data["status"] == "offen"
        ), f"Expected status 'offen', got {data.get('status')}"
        assert (
            data["ressource"] is None
        ), f"Expected ressource None, got {data.get('ressource')}"
        assert data["zugewiesen_at"] is None, "zugewiesen_at should be None"
        assert data["typ"] == "extern"
        assert data["ziel"] == "krankenhaus"
        assert data["incident_id"] == test_incident["id"]

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{data['id']}")

    def test_create_transport_with_ressource_status_zugewiesen(
        self, api_client, test_incident
    ):
        """POST with ressource should create transport with status=zugewiesen and zugewiesen_at set"""
        payload = {"typ": "intern", "ziel": "uhs", "ressource": "UHS Team 1"}
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports", json=payload
        )
        assert response.status_code == 201

        data = response.json()
        assert (
            data["status"] == "zugewiesen"
        ), f"Expected status 'zugewiesen', got {data.get('status')}"
        assert data["ressource"] == "UHS Team 1"
        assert data["zugewiesen_at"] is not None, "zugewiesen_at should be set"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{data['id']}")

    def test_create_transport_with_patient_copies_kennung_sichtung(
        self, api_client, test_incident
    ):
        """POST with patient_id should copy patient_kennung and patient_sichtung"""
        # Create a patient first
        patient_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S2"},
        )
        patient = patient_resp.json()

        payload = {"typ": "extern", "ziel": "krankenhaus", "patient_id": patient["id"]}
        response = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports", json=payload
        )
        assert response.status_code == 201

        data = response.json()
        assert data["patient_id"] == patient["id"]
        assert (
            data["patient_kennung"] == patient["kennung"]
        ), f"Expected kennung {patient['kennung']}, got {data.get('patient_kennung')}"
        assert (
            data["patient_sichtung"] == "S2"
        ), f"Expected sichtung S2, got {data.get('patient_sichtung')}"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{data['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{patient['id']}")


class TestTransportUpdate:
    """Tests for PATCH /api/transports/{id}"""

    def test_patch_ressource_sets_status_zugewiesen(self, api_client, test_incident):
        """PATCH with ressource='RTW 1' on offen transport sets status=zugewiesen"""
        # Create transport without ressource
        create_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports",
            json={"typ": "extern", "ziel": "krankenhaus"},
        )
        transport = create_resp.json()
        assert transport["status"] == "offen"

        # Update with ressource
        response = api_client.patch(
            f"{BASE_URL}/api/transports/{transport['id']}", json={"ressource": "RTW 1"}
        )
        assert response.status_code == 200

        data = response.json()
        assert (
            data["status"] == "zugewiesen"
        ), f"Expected status 'zugewiesen', got {data.get('status')}"
        assert data["ressource"] == "RTW 1"
        assert data["zugewiesen_at"] is not None, "zugewiesen_at should be set"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{transport['id']}")

    def test_patch_ressource_empty_removes_assignment(self, api_client, test_incident):
        """PATCH with ressource='' or null removes assignment (status=offen)"""
        # Create transport with ressource
        create_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports",
            json={"typ": "intern", "ziel": "uhs", "ressource": "UHS Team 2"},
        )
        transport = create_resp.json()
        assert transport["status"] == "zugewiesen"

        # Remove ressource
        response = api_client.patch(
            f"{BASE_URL}/api/transports/{transport['id']}", json={"ressource": ""}
        )
        assert response.status_code == 200

        data = response.json()
        assert (
            data["status"] == "offen"
        ), f"Expected status 'offen', got {data.get('status')}"
        assert data["ressource"] == ""

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{transport['id']}")

    def test_patch_status_unterwegs_sets_gestartet_at(self, api_client, test_incident):
        """PATCH with status=unterwegs sets gestartet_at"""
        # Create transport with ressource (zugewiesen)
        create_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports",
            json={"typ": "extern", "ziel": "krankenhaus", "ressource": "RTW 2"},
        )
        transport = create_resp.json()
        assert transport["status"] == "zugewiesen"
        assert transport["gestartet_at"] is None

        # Set status to unterwegs
        response = api_client.patch(
            f"{BASE_URL}/api/transports/{transport['id']}", json={"status": "unterwegs"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "unterwegs"
        assert data["gestartet_at"] is not None, "gestartet_at should be set"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{transport['id']}")

    def test_patch_status_abgeschlossen_sets_abgeschlossen_at(
        self, api_client, test_incident
    ):
        """PATCH with status=abgeschlossen sets abgeschlossen_at"""
        # Create transport with ressource
        create_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports",
            json={"typ": "intern", "ziel": "uhs", "ressource": "UHS Team 3"},
        )
        transport = create_resp.json()

        # Set status to unterwegs first
        api_client.patch(
            f"{BASE_URL}/api/transports/{transport['id']}", json={"status": "unterwegs"}
        )

        # Set status to abgeschlossen
        response = api_client.patch(
            f"{BASE_URL}/api/transports/{transport['id']}",
            json={"status": "abgeschlossen"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "abgeschlossen"
        assert data["abgeschlossen_at"] is not None, "abgeschlossen_at should be set"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{transport['id']}")

    def test_create_transport_on_planned_incident_returns_409(self, api_client):
        """POST transport on planned incident should be blocked."""
        incident_resp = api_client.post(
            f"{BASE_URL}/api/incidents",
            json={
                "name": "TEST_Planned_For_Transport_Block",
                "typ": "einsatz",
                "status": "geplant",
                "demo": False,
            },
        )
        assert incident_resp.status_code == 201
        incident_id = incident_resp.json()["id"]
        try:
            response = api_client.post(
                f"{BASE_URL}/api/incidents/{incident_id}/transports",
                json={"typ": "extern", "ziel": "krankenhaus"},
            )
            assert response.status_code == 409
        finally:
            api_client.delete(f"{BASE_URL}/api/incidents/{incident_id}")

    def test_patch_transport_on_planned_incident_returns_409(self, api_client):
        """PATCH transport should be blocked after incident switched to geplant."""
        incident_resp = api_client.post(
            f"{BASE_URL}/api/incidents",
            json={
                "name": "TEST_Planned_For_Transport_Update_Block",
                "typ": "einsatz",
                "status": "operativ",
                "demo": False,
            },
        )
        assert incident_resp.status_code == 201
        incident_id = incident_resp.json()["id"]
        try:
            create_resp = api_client.post(
                f"{BASE_URL}/api/incidents/{incident_id}/transports",
                json={"typ": "extern", "ziel": "krankenhaus"},
            )
            assert create_resp.status_code == 201
            transport_id = create_resp.json()["id"]

            patch_inc_resp = api_client.patch(
                f"{BASE_URL}/api/incidents/{incident_id}",
                json={"status": "geplant"},
            )
            assert patch_inc_resp.status_code == 200

            response = api_client.patch(
                f"{BASE_URL}/api/transports/{transport_id}",
                json={"ressource": "RTW 1"},
            )
            assert response.status_code == 409
        finally:
            api_client.delete(f"{BASE_URL}/api/incidents/{incident_id}")


class TestTransportDelete:
    """Tests for DELETE /api/transports/{id}"""

    def test_delete_transport_returns_204(self, api_client, test_incident):
        """DELETE /api/transports/{id} should return 204"""
        # Create transport
        create_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports",
            json={"typ": "extern", "ziel": "krankenhaus"},
        )
        transport = create_resp.json()

        # Delete
        response = api_client.delete(f"{BASE_URL}/api/transports/{transport['id']}")
        assert response.status_code == 204

        # Verify deleted
        get_resp = api_client.get(f"{BASE_URL}/api/transports/{transport['id']}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_transport_returns_404(self, api_client):
        """DELETE /api/transports/{nonexistent} should return 404"""
        response = api_client.delete(f"{BASE_URL}/api/transports/nonexistent-id")
        assert response.status_code == 404


class TestAutoCreateTransport:
    """Tests for Auto-Create: PATCH patient with transport_typ creates Transport"""

    def test_create_patient_with_transport_typ_creates_transport(
        self, api_client, test_incident
    ):
        """POST patient with transport_typ should create an assignable transport immediately."""
        patient_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S2", "transport_typ": "intern"},
        )
        assert patient_resp.status_code == 201
        patient = patient_resp.json()

        transports_resp = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports"
        )
        transports = transports_resp.json()
        patient_transport = next(
            (t for t in transports if t.get("patient_id") == patient["id"]), None
        )

        assert (
            patient_transport is not None
        ), "Expected transport to exist immediately after patient creation"
        assert patient_transport["typ"] == "intern"
        assert patient_transport["status"] == "offen"
        assert patient_transport["patient_kennung"] == patient["kennung"]

        api_client.delete(f"{BASE_URL}/api/transports/{patient_transport['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{patient['id']}")

    def test_patch_patient_transport_typ_intern_creates_transport(
        self, api_client, test_incident
    ):
        """PATCH patient with transport_typ=intern automatically creates Transport entry"""
        # Create patient
        patient_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S1"},
        )
        patient = patient_resp.json()

        # Set transport_typ
        api_client.patch(
            f"{BASE_URL}/api/patients/{patient['id']}", json={"transport_typ": "intern"}
        )

        # Check transports
        transports_resp = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports"
        )
        transports = transports_resp.json()

        # Find transport for this patient
        patient_transports = [
            t for t in transports if t.get("patient_id") == patient["id"]
        ]
        assert (
            len(patient_transports) >= 1
        ), f"Expected at least 1 transport for patient, found {len(patient_transports)}"

        transport = patient_transports[0]
        assert transport["typ"] == "intern"
        assert transport["status"] == "offen"
        assert transport["patient_kennung"] == patient["kennung"]
        assert transport["patient_sichtung"] == "S1"

        # Cleanup
        for t in patient_transports:
            api_client.delete(f"{BASE_URL}/api/transports/{t['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{patient['id']}")

    def test_patch_patient_transport_typ_extern_creates_transport(
        self, api_client, test_incident
    ):
        """PATCH patient with transport_typ=extern automatically creates Transport entry"""
        # Create patient
        patient_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S2"},
        )
        patient = patient_resp.json()

        # Set transport_typ
        api_client.patch(
            f"{BASE_URL}/api/patients/{patient['id']}", json={"transport_typ": "extern"}
        )

        # Check transports
        transports_resp = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports"
        )
        transports = transports_resp.json()

        # Find transport for this patient
        patient_transports = [
            t for t in transports if t.get("patient_id") == patient["id"]
        ]
        assert len(patient_transports) >= 1

        transport = patient_transports[0]
        assert transport["typ"] == "extern"
        assert (
            transport["ziel"] == "rd"
        ), f"Expected ziel 'rd' for extern, got {transport.get('ziel')}"

        # Cleanup
        for t in patient_transports:
            api_client.delete(f"{BASE_URL}/api/transports/{t['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{patient['id']}")

    def test_patch_patient_transport_typ_retargets_transport_and_releases_old_resource(
        self, api_client, test_incident
    ):
        """Changing patient transport typ should reopen the active transport for the new pool."""
        patient_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S1", "transport_typ": "extern"},
        )
        assert patient_resp.status_code == 201
        patient = patient_resp.json()

        transports_resp = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports"
        )
        transports = transports_resp.json()
        patient_transport = next(
            (t for t in transports if t.get("patient_id") == patient["id"]), None
        )
        assert patient_transport is not None

        assign_response = api_client.patch(
            f"{BASE_URL}/api/transports/{patient_transport['id']}",
            json={"ressource": "RTW 1"},
        )
        assert assign_response.status_code == 200

        change_response = api_client.patch(
            f"{BASE_URL}/api/patients/{patient['id']}",
            json={"transport_typ": "intern"},
        )
        assert change_response.status_code == 200

        updated_transport = api_client.get(
            f"{BASE_URL}/api/transports/{patient_transport['id']}"
        ).json()
        assert updated_transport["typ"] == "intern"
        assert updated_transport["ziel"] == "uhs"
        assert updated_transport["ressource"] is None
        assert updated_transport["status"] == "offen"

        resources = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/resources"
        ).json()
        rtw1 = next((r for r in resources if r["name"] == "RTW 1"), None)
        assert rtw1 is not None
        assert rtw1["status"] == "verfuegbar"

        api_client.delete(f"{BASE_URL}/api/transports/{patient_transport['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{patient['id']}")


class TestAutoCompleteTransport:
    """Tests for Auto-Complete: PATCH patient with status=entlassen/uebergeben completes transports"""

    def test_patch_patient_status_entlassen_completes_transports(
        self, api_client, test_incident
    ):
        """PATCH patient with status=entlassen sets associated transports to abgeschlossen"""
        # Create patient with transport
        patient_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S3"},
        )
        patient = patient_resp.json()
        api_client.patch(
            f"{BASE_URL}/api/patients/{patient['id']}", json={"transport_typ": "intern"}
        )

        # Get transport
        transports_resp = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports"
        )
        transports = transports_resp.json()
        patient_transport = next(
            (t for t in transports if t.get("patient_id") == patient["id"]), None
        )
        assert patient_transport is not None
        assert patient_transport["status"] != "abgeschlossen"

        # Set patient status to entlassen
        api_client.patch(
            f"{BASE_URL}/api/patients/{patient['id']}", json={"status": "entlassen"}
        )

        # Check transport is now abgeschlossen
        transport_resp = api_client.get(
            f"{BASE_URL}/api/transports/{patient_transport['id']}"
        )
        updated_transport = transport_resp.json()
        assert (
            updated_transport["status"] == "abgeschlossen"
        ), f"Expected status 'abgeschlossen', got {updated_transport.get('status')}"
        assert updated_transport["abgeschlossen_at"] is not None

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{patient_transport['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{patient['id']}")

    def test_patch_patient_status_uebergeben_completes_transports(
        self, api_client, test_incident
    ):
        """PATCH patient with status=uebergeben sets associated transports to abgeschlossen"""
        # Create patient with transport
        patient_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/patients",
            json={"sichtung": "S1"},
        )
        patient = patient_resp.json()
        api_client.patch(
            f"{BASE_URL}/api/patients/{patient['id']}", json={"transport_typ": "extern"}
        )

        # Get transport
        transports_resp = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports"
        )
        transports = transports_resp.json()
        patient_transport = next(
            (t for t in transports if t.get("patient_id") == patient["id"]), None
        )
        assert patient_transport is not None

        # Set patient status to uebergeben
        api_client.patch(
            f"{BASE_URL}/api/patients/{patient['id']}", json={"status": "uebergeben"}
        )

        # Check transport is now abgeschlossen
        transport_resp = api_client.get(
            f"{BASE_URL}/api/transports/{patient_transport['id']}"
        )
        updated_transport = transport_resp.json()
        assert updated_transport["status"] == "abgeschlossen"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{patient_transport['id']}")
        api_client.delete(f"{BASE_URL}/api/patients/{patient['id']}")


class TestCascadeDelete:
    """Tests for cascade delete: DELETE incident removes transports"""

    def test_delete_incident_removes_transports(self, api_client):
        """DELETE incident should remove all associated transports"""
        # Create incident
        incident_resp = api_client.post(
            f"{BASE_URL}/api/incidents",
            json={
                "name": "TEST_Cascade_Delete_Incident",
                "typ": "uebung",
                "status": "operativ",
            },
        )
        incident = incident_resp.json()

        # Create transport
        transport_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{incident['id']}/transports",
            json={"typ": "extern", "ziel": "krankenhaus"},
        )
        transport = transport_resp.json()

        # Delete incident
        api_client.delete(f"{BASE_URL}/api/incidents/{incident['id']}")

        # Verify transport is gone
        get_resp = api_client.get(f"{BASE_URL}/api/transports/{transport['id']}")
        assert get_resp.status_code == 404, "Transport should be deleted with incident"


class TestTransportFiltering:
    """Tests for filtering transports by typ and status"""

    def test_filter_by_typ_intern(self, api_client, test_incident):
        """GET with ?typ=intern filters correctly"""
        # Create intern and extern transports
        intern_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports",
            json={"typ": "intern", "ziel": "uhs"},
        )
        extern_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports",
            json={"typ": "extern", "ziel": "krankenhaus"},
        )
        intern_t = intern_resp.json()
        extern_t = extern_resp.json()

        # Filter by typ=intern
        response = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports?typ=intern"
        )
        assert response.status_code == 200

        data = response.json()
        for t in data:
            assert t["typ"] == "intern", f"Expected typ 'intern', got {t.get('typ')}"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{intern_t['id']}")
        api_client.delete(f"{BASE_URL}/api/transports/{extern_t['id']}")

    def test_filter_by_status_offen(self, api_client, test_incident):
        """GET with ?status=offen filters correctly"""
        # Create offen and zugewiesen transports
        offen_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports",
            json={"typ": "extern", "ziel": "krankenhaus"},
        )
        zugewiesen_resp = api_client.post(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports",
            json={"typ": "intern", "ziel": "uhs", "ressource": "UHS Team 1"},
        )
        offen_t = offen_resp.json()
        zugewiesen_t = zugewiesen_resp.json()

        # Filter by status=offen
        response = api_client.get(
            f"{BASE_URL}/api/incidents/{test_incident['id']}/transports?status=offen"
        )
        assert response.status_code == 200

        data = response.json()
        for t in data:
            assert (
                t["status"] == "offen"
            ), f"Expected status 'offen', got {t.get('status')}"

        # Cleanup
        api_client.delete(f"{BASE_URL}/api/transports/{offen_t['id']}")
        api_client.delete(f"{BASE_URL}/api/transports/{zugewiesen_t['id']}")
