"""Regression tests: EVT rename + resource delete persistence (no re-seed)."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def _create_demo_incident():
    r = requests.post(f"{BASE_URL}/api/incidents/demo", timeout=30)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


class TestEvtRename:
    def test_default_resources_contain_evt_not_radstreife(self):
        incident_id = _create_demo_incident()
        r = requests.get(f"{BASE_URL}/api/incidents/{incident_id}/resources", timeout=15)
        assert r.status_code == 200
        resources = r.json()
        assert len(resources) == 9, f"Expected 9 default resources, got {len(resources)}"

        names = [x["name"] for x in resources]
        kats = [x["kategorie"] for x in resources]

        assert "EVT 1" in names, f"EVT 1 not in default resources: {names}"
        assert "evt" in kats, f"kategorie 'evt' not present: {kats}"

        # No radstreife relics
        assert not any("Radstreife" in n for n in names), f"Legacy Radstreife found: {names}"
        assert "bike" not in kats, f"Legacy bike kategorie found: {kats}"

        evt = next(x for x in resources if x["name"] == "EVT 1")
        assert evt["typ"] == "intern"
        assert evt["kategorie"] == "evt"


class TestDeletePersistence:
    def test_delete_single_resource_persists_and_no_reseed(self):
        incident_id = _create_demo_incident()
        r = requests.get(f"{BASE_URL}/api/incidents/{incident_id}/resources", timeout=15)
        resources = r.json()
        evt = next(x for x in resources if x["name"] == "EVT 1")

        d = requests.delete(f"{BASE_URL}/api/resources/{evt['id']}", timeout=15)
        assert d.status_code == 204

        # Confirm gone
        r2 = requests.get(f"{BASE_URL}/api/incidents/{incident_id}/resources", timeout=15)
        names2 = [x["name"] for x in r2.json()]
        assert "EVT 1" not in names2
        assert len(r2.json()) == 8

        # Second GET: still gone (no re-seed)
        r3 = requests.get(f"{BASE_URL}/api/incidents/{incident_id}/resources", timeout=15)
        assert len(r3.json()) == 8
        assert "EVT 1" not in [x["name"] for x in r3.json()]

    def test_delete_all_resources_no_reseed_on_empty(self):
        incident_id = _create_demo_incident()
        r = requests.get(f"{BASE_URL}/api/incidents/{incident_id}/resources", timeout=15)
        resources = r.json()

        for res in resources:
            d = requests.delete(f"{BASE_URL}/api/resources/{res['id']}", timeout=15)
            assert d.status_code == 204, f"Failed deleting {res['name']}"

        r2 = requests.get(f"{BASE_URL}/api/incidents/{incident_id}/resources", timeout=15)
        assert r2.status_code == 200
        assert r2.json() == [], f"Expected empty, got {r2.json()}"

        # Second GET – still empty (regression guard for previous re-seed behaviour)
        r3 = requests.get(f"{BASE_URL}/api/incidents/{incident_id}/resources", timeout=15)
        assert r3.json() == []

    def test_create_custom_resource_then_delete_persists(self):
        incident_id = _create_demo_incident()

        # Create custom resource
        payload = {
            "name": "TEST_Testwagen 1",
            "typ": "intern",
            "kategorie": "sonstiges",
        }
        c = requests.post(
            f"{BASE_URL}/api/incidents/{incident_id}/resources",
            json=payload,
            timeout=15,
        )
        assert c.status_code == 201
        new_id = c.json()["id"]
        assert c.json()["name"] == "TEST_Testwagen 1"
        assert c.json()["kategorie"] == "sonstiges"

        # GET verifies persistence
        r = requests.get(f"{BASE_URL}/api/incidents/{incident_id}/resources", timeout=15)
        assert any(x["id"] == new_id for x in r.json())

        # Delete
        d = requests.delete(f"{BASE_URL}/api/resources/{new_id}", timeout=15)
        assert d.status_code == 204

        r2 = requests.get(f"{BASE_URL}/api/incidents/{incident_id}/resources", timeout=15)
        assert not any(x["id"] == new_id for x in r2.json())
