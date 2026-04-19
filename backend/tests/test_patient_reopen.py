"""Tests for POST /api/patients/{id}/reopen endpoint (wiedereroeffnen)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def demo_incident():
    r = requests.post(f"{API}/incidents/demo", timeout=15)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    inc_id = data.get("incident", {}).get("id") or data.get("id")
    assert inc_id
    return inc_id


@pytest.fixture(scope="module")
def patients(demo_incident):
    r = requests.get(f"{API}/incidents/{demo_incident}/patients", timeout=10)
    assert r.status_code == 200
    return r.json()


def _find_by_status(patients, status):
    return next((p for p in patients if p.get("status") == status), None)


class TestReopenEndpoint:
    def test_404_nonexistent(self):
        r = requests.post(f"{API}/patients/does-not-exist/reopen", timeout=10)
        assert r.status_code == 404

    def test_409_non_closed(self, patients):
        open_p = _find_by_status(patients, "in_behandlung")
        assert open_p, "demo must have an open patient"
        r = requests.post(f"{API}/patients/{open_p['id']}/reopen", timeout=10)
        assert r.status_code == 409
        body = r.json()
        assert "wiedereroeffnet" in (body.get("detail", "").lower())

    def test_reopen_closed_patient_success(self, demo_incident, patients):
        closed = _find_by_status(patients, "entlassen") or _find_by_status(patients, "uebergeben")
        assert closed, "demo must have a closed patient"
        pid = closed["id"]
        kennung = closed["kennung"]

        r = requests.post(f"{API}/patients/{pid}/reopen", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "in_behandlung"
        assert data.get("fallabschluss_typ") in (None, "")
        assert data.get("fallabschluss_at") in (None, "")
        assert data["verbleib"] == "unbekannt"
        assert isinstance(data.get("wiedereroeffnet_at"), list)
        assert len(data["wiedereroeffnet_at"]) == 1

        # GET persistence
        g = requests.get(f"{API}/patients/{pid}", timeout=10)
        assert g.status_code == 200
        gd = g.json()
        assert gd["status"] == "in_behandlung"
        assert len(gd["wiedereroeffnet_at"]) == 1

        # system funk entry
        m = requests.get(f"{API}/incidents/{demo_incident}/messages", timeout=10)
        assert m.status_code == 200
        msgs = m.json()
        hits = [
            x for x in msgs
            if x.get("patient_id") == pid
            and x.get("funk_typ") == "system"
            and "wiedereroeffnet" in x.get("text", "").lower()
            and kennung in x.get("text", "")
        ]
        assert hits, "system funk entry for reopen must be logged"

    def test_multiple_reopens_append_history(self, demo_incident, patients):
        # Use second closed patient for isolation
        closed_list = [p for p in patients if p.get("status") in ("uebergeben", "entlassen")]
        # Already used the first one in prior test, pick another
        # Re-fetch to pick a still-closed one
        r = requests.get(f"{API}/incidents/{demo_incident}/patients", timeout=10)
        closed_list = [p for p in r.json() if p.get("status") in ("uebergeben", "entlassen")]
        assert closed_list, "need another closed patient"
        pid = closed_list[0]["id"]

        # 1st reopen
        r1 = requests.post(f"{API}/patients/{pid}/reopen", timeout=10)
        assert r1.status_code == 200
        assert len(r1.json()["wiedereroeffnet_at"]) == 1

        # close again via PATCH
        pc = requests.patch(
            f"{API}/patients/{pid}",
            json={"fallabschluss_typ": "entlassung"},
            timeout=10,
        )
        assert pc.status_code == 200, pc.text
        assert pc.json()["status"] == "entlassen"

        # 2nd reopen → list length = 2
        r2 = requests.post(f"{API}/patients/{pid}/reopen", timeout=10)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["status"] == "in_behandlung"
        assert len(d2["wiedereroeffnet_at"]) == 2
        assert d2.get("fallabschluss_typ") in (None, "")

    def test_wiedereroeffnet_at_default_empty_list(self, patients):
        # every patient should expose field (empty list) or missing is acceptable
        for p in patients:
            val = p.get("wiedereroeffnet_at", [])
            assert isinstance(val, list)
