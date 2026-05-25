"""Tests for FMS-Alarm Quittierung (acknowledge_fms_event + POST /api/fms-events/{id}/acknowledge).

Covers:
- 200 mit role=einsatzleiter -> setzt acknowledged_by_role + acknowledged_at
- 200 mit role=fuehrungsassistenz
- 403 mit role=helfer
- 409 doppelte Quittierung
- 409 nicht-Alert-Event (to_fms NICHT in {0,5})
- 404 nicht existierendes Event
- GET /api/incidents/{id}/fms-events liefert is_alert/acknowledged_by_role/acknowledged_at
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def incident_id():
    payload = {"name": f"TEST_FMS_ACK_{uuid.uuid4().hex[:6]}", "meldebild": "ack test"}
    r = requests.post(f"{API}/incidents", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    inc = r.json()
    yield inc["id"]
    try:
        requests.delete(f"{API}/incidents/{inc['id']}", timeout=10)
    except Exception:
        pass


@pytest.fixture
def resource(incident_id):
    r = requests.post(
        f"{API}/incidents/{incident_id}/resources",
        json={"name": "TEST_ACK_VEH", "typ": "intern", "kategorie": "rtw"},
        timeout=10,
    )
    assert r.status_code == 201, r.text
    res = r.json()
    yield res
    try:
        requests.delete(f"{API}/resources/{res['id']}", timeout=10)
    except Exception:
        pass


def _create_event(incident_id: str, resource_id: str, to_fms: int) -> dict:
    """Trigger creation of an fms_event via PATCH and return the latest event."""
    r = requests.patch(
        f"{API}/resources/{resource_id}", json={"fms_status": to_fms}, timeout=10
    )
    assert r.status_code == 200, r.text
    events = requests.get(
        f"{API}/incidents/{incident_id}/fms-events",
        params={"resource_id": resource_id},
        timeout=10,
    ).json()
    assert events, "expected at least 1 event after PATCH"
    return events[0]


class TestAcknowledgeEndpoint:
    def test_listing_contains_new_alert_fields(self, incident_id, resource):
        evt = _create_event(incident_id, resource["id"], 5)
        assert evt["to_fms"] == 5
        assert evt.get("is_alert") is True
        # initially unacknowledged
        assert evt.get("acknowledged_by_role") in (None, "")
        assert evt.get("acknowledged_at") in (None, "")

    def test_acknowledge_with_einsatzleiter_returns_200(self, incident_id, resource):
        evt = _create_event(incident_id, resource["id"], 5)
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "einsatzleiter"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["acknowledged_by_role"] == "einsatzleiter"
        assert body["acknowledged_at"], "acknowledged_at must be ISO string"
        # Persisted via GET
        events = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": resource["id"]},
            timeout=10,
        ).json()
        match = next((e for e in events if e["id"] == evt["id"]), None)
        assert match is not None
        assert match["acknowledged_by_role"] == "einsatzleiter"
        assert match["acknowledged_at"]

    def test_acknowledge_with_fuehrungsassistenz_returns_200(self, incident_id, resource):
        # use FMS 0 this time (the other alert code)
        evt = _create_event(incident_id, resource["id"], 0)
        assert evt.get("is_alert") is True
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "fuehrungsassistenz"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json()["acknowledged_by_role"] == "fuehrungsassistenz"

    def test_acknowledge_with_helfer_returns_403(self, incident_id, resource):
        evt = _create_event(incident_id, resource["id"], 5)
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "helfer"},
            timeout=10,
        )
        assert r.status_code == 403, r.text
        body = r.json()
        assert "Einsatzleiter" in (body.get("detail") or "") or "Fuehrungsassistenz" in (
            body.get("detail") or ""
        )

    def test_double_acknowledge_returns_409(self, incident_id, resource):
        evt = _create_event(incident_id, resource["id"], 5)
        r1 = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "einsatzleiter"},
            timeout=10,
        )
        assert r1.status_code == 200
        r2 = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "einsatzleiter"},
            timeout=10,
        )
        assert r2.status_code == 409, r2.text

    def test_acknowledge_non_alert_event_returns_409(self, incident_id, resource):
        # FMS 3 = not in {0,5}
        evt = _create_event(incident_id, resource["id"], 3)
        assert evt.get("is_alert") is False
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "einsatzleiter"},
            timeout=10,
        )
        assert r.status_code == 409, r.text
        assert "FMS-5/0" in (r.json().get("detail") or "")

    def test_acknowledge_unknown_event_returns_404(self):
        fake_id = uuid.uuid4().hex
        r = requests.post(
            f"{API}/fms-events/{fake_id}/acknowledge",
            json={"role": "einsatzleiter"},
            timeout=10,
        )
        assert r.status_code == 404, r.text
