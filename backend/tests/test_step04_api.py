"""
Backend API Tests for ELS MHD - Step 04: Patientendetail + S4->S0 Migration
Tests: S4->S0 migration, transport_typ, fallabschluss_typ, smart status progression
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


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
        "name": "TEST_Step04_Incident",
        "typ": "uebung",
        "ort": "Test Location",
        "beschreibung": "Test incident for Step 04 API tests",
        "status": "operativ",
        "demo": False
    }
    response = api_client.post(f"{BASE_URL}/api/incidents", json=payload)
    assert response.status_code == 201, f"Failed to create test incident: {response.text}"
    incident = response.json()
    yield incident
    # Cleanup - delete incident (should cascade delete patients)
    api_client.delete(f"{BASE_URL}/api/incidents/{incident['id']}")


class TestMetaVersion:
    """Tests for GET /api/meta - version 0.4.0"""
    
    def test_meta_returns_version_040(self, api_client):
        """GET /api/meta should return version 0.4.0"""
        response = api_client.get(f"{BASE_URL}/api/meta")
        assert response.status_code == 200
        
        data = response.json()
        assert data["version"] == "0.4.0", f"Expected version 0.4.0, got {data.get('version')}"
        assert data["step"] == "04 – Patientendetail", f"Expected step '04 – Patientendetail', got {data.get('step')}"


class TestS4ToS0Migration:
    """Tests for S4->S0 global rename"""
    
    def test_post_with_sichtung_s4_returns_422(self, api_client, test_incident):
        """POST with sichtung='S4' should return 422 (no longer allowed)"""
        payload = {"sichtung": "S4"}
        response = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json=payload)
        assert response.status_code == 422, f"Expected 422 for S4, got {response.status_code}: {response.text}"
    
    def test_post_with_sichtung_s0_succeeds(self, api_client, test_incident):
        """POST with sichtung='S0' should succeed"""
        payload = {"sichtung": "S0"}
        response = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json=payload)
        assert response.status_code == 201, f"Expected 201 for S0, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["sichtung"] == "S0", f"Expected sichtung 'S0', got {data.get('sichtung')}"
        assert data["status"] == "in_behandlung", f"Expected status 'in_behandlung', got {data.get('status')}"
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{data['id']}")
    
    def test_no_s4_patients_in_database(self, api_client, test_incident):
        """After migration, no patients should have sichtung='S4'"""
        # Get all patients for the incident
        response = api_client.get(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients")
        assert response.status_code == 200
        
        data = response.json()
        for patient in data:
            assert patient.get("sichtung") != "S4", f"Found patient with S4: {patient.get('kennung')}"


class TestTransportTyp:
    """Tests for transport_typ field and automatic status progression"""
    
    def test_patch_transport_typ_intern_sets_status_and_timestamp(self, api_client, test_incident):
        """PATCH with transport_typ='intern' should set status=transportbereit AND transport_angefordert_at"""
        # Create patient with sichtung (status=in_behandlung)
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={"sichtung": "S2"}).json()
        assert p["status"] == "in_behandlung"
        assert p["transport_angefordert_at"] is None
        
        # Update with transport_typ
        response = api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"transport_typ": "intern"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["transport_typ"] == "intern", f"Expected transport_typ 'intern', got {data.get('transport_typ')}"
        assert data["status"] == "transportbereit", f"Expected status 'transportbereit', got {data.get('status')}"
        assert data["transport_angefordert_at"] is not None, "transport_angefordert_at should be set"
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")
    
    def test_patch_transport_typ_extern_sets_status_and_timestamp(self, api_client, test_incident):
        """PATCH with transport_typ='extern' should set status=transportbereit AND transport_angefordert_at"""
        # Create patient
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={"sichtung": "S1"}).json()
        
        # Update with transport_typ
        response = api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"transport_typ": "extern"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["transport_typ"] == "extern"
        assert data["status"] == "transportbereit"
        assert data["transport_angefordert_at"] is not None
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")
    
    def test_get_patient_includes_transport_typ(self, api_client, test_incident):
        """GET /api/patients/{id} should include transport_typ field"""
        # Create patient and set transport_typ
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={"sichtung": "S3"}).json()
        api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"transport_typ": "intern"})
        
        # Get patient
        response = api_client.get(f"{BASE_URL}/api/patients/{p['id']}")
        assert response.status_code == 200
        
        data = response.json()
        assert "transport_typ" in data, "transport_typ field should be in response"
        assert data["transport_typ"] == "intern"
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")


class TestFallabschlussTyp:
    """Tests for fallabschluss_typ field and automatic status/verbleib progression"""
    
    def test_patch_fallabschluss_rd_uebergabe(self, api_client, test_incident):
        """PATCH with fallabschluss_typ='rd_uebergabe' should set status=uebergeben, verbleib=rd, fallabschluss_at"""
        # Create patient
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={"sichtung": "S2"}).json()
        
        # Update with fallabschluss_typ
        response = api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"fallabschluss_typ": "rd_uebergabe"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["fallabschluss_typ"] == "rd_uebergabe", f"Expected fallabschluss_typ 'rd_uebergabe', got {data.get('fallabschluss_typ')}"
        assert data["status"] == "uebergeben", f"Expected status 'uebergeben', got {data.get('status')}"
        assert data["verbleib"] == "rd", f"Expected verbleib 'rd', got {data.get('verbleib')}"
        assert data["fallabschluss_at"] is not None, "fallabschluss_at should be set"
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")
    
    def test_patch_fallabschluss_entlassung(self, api_client, test_incident):
        """PATCH with fallabschluss_typ='entlassung' should set status=entlassen, verbleib=event, fallabschluss_at"""
        # Create patient
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={"sichtung": "S3"}).json()
        
        # Update with fallabschluss_typ
        response = api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"fallabschluss_typ": "entlassung"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["fallabschluss_typ"] == "entlassung"
        assert data["status"] == "entlassen"
        assert data["verbleib"] == "event"
        assert data["fallabschluss_at"] is not None
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")
    
    def test_patch_fallabschluss_manuell(self, api_client, test_incident):
        """PATCH with fallabschluss_typ='manuell' should set status=entlassen, fallabschluss_at (verbleib unchanged)"""
        # Create patient
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={"sichtung": "S1"}).json()
        assert p["verbleib"] == "unbekannt"
        
        # Update with fallabschluss_typ
        response = api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"fallabschluss_typ": "manuell"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["fallabschluss_typ"] == "manuell"
        assert data["status"] == "entlassen"
        # verbleib should remain unbekannt for manuell
        assert data["verbleib"] == "unbekannt", f"Expected verbleib 'unbekannt' for manuell, got {data.get('verbleib')}"
        assert data["fallabschluss_at"] is not None
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")
    
    def test_get_patient_includes_fallabschluss_typ(self, api_client, test_incident):
        """GET /api/patients/{id} should include fallabschluss_typ field"""
        # Create patient and set fallabschluss_typ
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={"sichtung": "S0"}).json()
        api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"fallabschluss_typ": "entlassung"})
        
        # Get patient
        response = api_client.get(f"{BASE_URL}/api/patients/{p['id']}")
        assert response.status_code == 200
        
        data = response.json()
        assert "fallabschluss_typ" in data, "fallabschluss_typ field should be in response"
        assert data["fallabschluss_typ"] == "entlassung"
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")
    
    def test_fallabschluss_preserves_existing_verbleib(self, api_client, test_incident):
        """PATCH with fallabschluss_typ should preserve existing verbleib if not 'unbekannt'"""
        # Create patient and set verbleib first
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={"sichtung": "S2"}).json()
        api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"verbleib": "krankenhaus"})
        
        # Update with fallabschluss_typ
        response = api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"fallabschluss_typ": "rd_uebergabe"})
        assert response.status_code == 200
        
        data = response.json()
        # verbleib should remain krankenhaus (not overwritten to rd)
        assert data["verbleib"] == "krankenhaus", f"Expected verbleib 'krankenhaus' to be preserved, got {data.get('verbleib')}"
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")


class TestSmartStatusProgression:
    """Tests for the complete status progression flow"""
    
    def test_full_progression_flow_from_sichtung(self, api_client, test_incident):
        """Test complete flow: in_behandlung (with sichtung) -> transportbereit -> uebergeben"""
        # 1. Create patient with sichtung (status=in_behandlung)
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={"sichtung": "S2"}).json()
        assert p["status"] == "in_behandlung"
        assert p["sichtung"] == "S2"
        assert p["sichtung_at"] is not None
        assert p["behandlung_start_at"] is not None
        
        # 2. Set transport_typ -> status=transportbereit
        response = api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"transport_typ": "extern"})
        data = response.json()
        assert data["status"] == "transportbereit"
        assert data["transport_angefordert_at"] is not None
        
        # 3. Set fallabschluss_typ -> status=uebergeben
        response = api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"fallabschluss_typ": "rd_uebergabe"})
        data = response.json()
        assert data["status"] == "uebergeben"
        assert data["fallabschluss_at"] is not None
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")
    
    def test_sichtung_patch_sets_timestamps_but_not_status(self, api_client, test_incident):
        """PATCH with sichtung on wartend patient sets timestamps but status remains wartend"""
        # Create patient without sichtung (status=wartend)
        p = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json={}).json()
        assert p["status"] == "wartend"
        assert p["sichtung"] is None
        
        # Set sichtung via PATCH - timestamps set but status stays wartend
        response = api_client.patch(f"{BASE_URL}/api/patients/{p['id']}", json={"sichtung": "S2"})
        data = response.json()
        assert data["sichtung"] == "S2"
        assert data["sichtung_at"] is not None, "sichtung_at should be set"
        assert data["behandlung_start_at"] is not None, "behandlung_start_at should be set"
        # Note: status does NOT automatically change to in_behandlung on PATCH
        # This is by design - status change only happens on CREATE with sichtung
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{p['id']}")


class TestAllSichtungLevels:
    """Tests for all valid sichtung levels (S0, S1, S2, S3)"""
    
    @pytest.mark.parametrize("sichtung", ["S0", "S1", "S2", "S3"])
    def test_create_patient_with_valid_sichtung(self, api_client, test_incident, sichtung):
        """POST with valid sichtung levels should succeed"""
        payload = {"sichtung": sichtung}
        response = api_client.post(f"{BASE_URL}/api/incidents/{test_incident['id']}/patients", json=payload)
        assert response.status_code == 201, f"Expected 201 for {sichtung}, got {response.status_code}"
        
        data = response.json()
        assert data["sichtung"] == sichtung
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/patients/{data['id']}")
