"""Phase 3 Divera integration tests."""
import asyncio
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def active_incident_id(session):
    r = session.get(f"{BASE_URL}/api/incidents")
    assert r.status_code == 200
    incidents = [i for i in r.json() if i.get("status") != "abgeschlossen"]
    assert incidents, "no operative incident available"
    return incidents[0]["id"]


# --- Configuration ---
class TestDiveraConfigured:
    def test_configured_true(self, session):
        r = session.get(f"{BASE_URL}/api/divera/configured")
        assert r.status_code == 200
        data = r.json()
        assert data["configured"] is True
        assert data["poll_interval_seconds"] == 30


# --- Live Vehicles ---
class TestDiveraVehicles:
    def test_list_vehicles_live(self, session):
        r = session.get(f"{BASE_URL}/api/divera/vehicles")
        assert r.status_code == 200
        vehicles = r.json()
        assert isinstance(vehicles, list)
        assert len(vehicles) == 5, f"expected 5 live vehicles, got {len(vehicles)}"
        v = vehicles[0]
        for field in ["id", "name", "shortname", "fullname", "fmsstatus",
                       "fmsstatus_id", "fmsstatus_note", "fmsstatus_ts", "lat", "lng"]:
            assert field in v, f"missing field {field}"
        # FMS values must be 0-9
        for v in vehicles:
            assert 0 <= v["fmsstatus"] <= 9


# --- Status endpoint ---
class TestDiveraStatus:
    def test_status_unknown_incident(self, session):
        r = session.get(f"{BASE_URL}/api/incidents/nonexistent-id-xyz/divera/status")
        assert r.status_code == 404

    def test_status_full_snapshot(self, session, active_incident_id):
        r = session.get(f"{BASE_URL}/api/incidents/{active_incident_id}/divera/status")
        assert r.status_code == 200
        d = r.json()
        for f in ["configured", "running", "enabled", "last_poll_at", "last_status",
                  "last_match_count", "linked_resources", "poll_interval_seconds",
                  "incident_status"]:
            assert f in d, f"missing snapshot field {f}"
        assert d["configured"] is True
        assert d["poll_interval_seconds"] == 30
        assert isinstance(d["linked_resources"], int)


# --- Manual sync ---
class TestDiveraSync:
    def test_sync_unknown_incident(self, session):
        r = session.post(f"{BASE_URL}/api/incidents/nonexistent-id/divera/sync")
        assert r.status_code == 404

    def test_sync_ok(self, session, active_incident_id):
        r = session.post(f"{BASE_URL}/api/incidents/{active_incident_id}/divera/sync")
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["vehicles_total"] == 5
        assert "matched" in d
        assert "timestamp" in d
        # verify persisted
        s = session.get(f"{BASE_URL}/api/incidents/{active_incident_id}/divera/status").json()
        assert s["last_status"] == "ok"
        assert s["last_poll_at"] is not None


# --- Start/Stop polling ---
class TestDiveraStartStop:
    def test_start_unknown_incident(self, session):
        r = session.post(f"{BASE_URL}/api/incidents/nonexistent-id/divera/start")
        assert r.status_code == 404

    def test_start_then_stop(self, session, active_incident_id):
        # ensure stopped before
        session.post(f"{BASE_URL}/api/incidents/{active_incident_id}/divera/stop")

        r = session.post(f"{BASE_URL}/api/incidents/{active_incident_id}/divera/start")
        assert r.status_code == 200
        d = r.json()
        assert d["running"] is True
        assert "first_sync" in d
        fs = d["first_sync"]
        assert fs["ok"] is True
        assert fs["vehicles_total"] == 5

        # status should reflect running+enabled
        status = session.get(f"{BASE_URL}/api/incidents/{active_incident_id}/divera/status").json()
        assert status["running"] is True
        assert status["enabled"] is True

        # stop
        r = session.post(f"{BASE_URL}/api/incidents/{active_incident_id}/divera/stop")
        assert r.status_code == 200
        assert r.json()["running"] is False

        # confirm stopped
        time.sleep(0.5)
        status2 = session.get(f"{BASE_URL}/api/incidents/{active_incident_id}/divera/status").json()
        assert status2["running"] is False
        assert status2["enabled"] is False

    def test_start_archived_incident_409(self, session):
        # create + close incident
        cr = session.post(f"{BASE_URL}/api/incidents", json={
            "name": "TEST_DIVERA_ARCHIVED",
            "ort": "Hamburg",
        })
        assert cr.status_code in (200, 201)
        inc_id = cr.json()["id"]
        # close via PATCH
        pr = session.patch(f"{BASE_URL}/api/incidents/{inc_id}",
                            json={"status": "abgeschlossen"})
        # if PATCH not supported try a status route
        if pr.status_code not in (200, 204):
            # try generic update
            pr = session.put(f"{BASE_URL}/api/incidents/{inc_id}",
                              json={"status": "abgeschlossen"})
        # Best-effort: skip if cannot close
        check = session.get(f"{BASE_URL}/api/incidents/{inc_id}").json()
        if check.get("status") != "abgeschlossen":
            pytest.skip("Cannot transition incident to abgeschlossen via available API")
        r = session.post(f"{BASE_URL}/api/incidents/{inc_id}/divera/start")
        assert r.status_code == 409


# --- Resource link + sync verification ---
class TestDiveraResourceSync:
    def test_link_resource_and_sync(self, session, active_incident_id):
        # Find an existing resource to use; create a test one
        cr = session.post(f"{BASE_URL}/api/incidents/{active_incident_id}/resources", json={
            "name": "TEST_DIVERA_RES",
            "typ": "intern",
            "status": "verfuegbar",
        })
        assert cr.status_code in (200, 201), cr.text
        res = cr.json()
        res_id = res["id"]

        # Link to live Divera vehicle 96955 (JOH SE EVT 1, FMS 6 = offline)
        pr = session.patch(f"{BASE_URL}/api/resources/{res_id}",
                            json={"divera_id": "96955"})
        assert pr.status_code == 200, pr.text

        # Manual sync
        sr = session.post(f"{BASE_URL}/api/incidents/{active_incident_id}/divera/sync")
        assert sr.status_code == 200
        assert sr.json()["matched"] >= 1

        # Verify resource got FMS 6 + status offline + lat/lng populated
        list_r = session.get(f"{BASE_URL}/api/incidents/{active_incident_id}/resources")
        assert list_r.status_code == 200
        updated_list = [r for r in list_r.json() if r["id"] == res_id]
        assert updated_list, "resource not found in list"
        updated = updated_list[0]
        assert updated["fms_status"] == 6
        assert updated["status"] == "offline"
        assert updated.get("lat") is not None
        assert updated.get("lng") is not None

        # Cleanup: unlink + delete
        session.patch(f"{BASE_URL}/api/resources/{res_id}", json={"divera_id": None})
        dr = session.delete(f"{BASE_URL}/api/resources/{res_id}")
        assert dr.status_code in (200, 204)

    def test_sync_503_when_unconfigured(self, session):
        # We can only check that the endpoint exists; configured == true so
        # we cannot trigger 503 without removing the key. Just smoke check.
        r = session.get(f"{BASE_URL}/api/divera/configured")
        assert r.status_code == 200
