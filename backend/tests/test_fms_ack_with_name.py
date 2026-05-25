"""Tests for new optional `name` field on POST /api/fms-events/{id}/acknowledge (iteration 22).

Covers:
- 200 mit role+name -> acknowledged_by_name persistiert (Create→GET)
- 200 ohne name -> acknowledged_by_name = None (Backward-Compat)
- 200 name=' ' (whitespace only) -> normalisiert zu None
- 422 name > 120 Zeichen (Pydantic max_length)
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
    payload = {"name": f"TEST_ACK_NAME_{uuid.uuid4().hex[:6]}", "meldebild": "ack name test"}
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
        json={"name": "TEST_ACK_NAME_VEH", "typ": "intern", "kategorie": "rtw"},
        timeout=10,
    )
    assert r.status_code == 201, r.text
    res = r.json()
    yield res
    try:
        requests.delete(f"{API}/resources/{res['id']}", timeout=10)
    except Exception:
        pass


def _create_alert_event(incident_id: str, resource_id: str) -> dict:
    r = requests.patch(
        f"{API}/resources/{resource_id}", json={"fms_status": 5}, timeout=10
    )
    assert r.status_code == 200, r.text
    events = requests.get(
        f"{API}/incidents/{incident_id}/fms-events",
        params={"resource_id": resource_id},
        timeout=10,
    ).json()
    assert events
    return events[0]


class TestAcknowledgeWithName:
    def test_ack_with_role_and_name_persists_acknowledged_by_name(self, incident_id, resource):
        evt = _create_alert_event(incident_id, resource["id"])
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "einsatzleiter", "name": "Max Mustermann"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["acknowledged_by_role"] == "einsatzleiter"
        assert body["acknowledged_by_name"] == "Max Mustermann"
        assert body["acknowledged_at"]

        # GET to verify persistence in MongoDB
        events = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": resource["id"]},
            timeout=10,
        ).json()
        match = next((e for e in events if e["id"] == evt["id"]), None)
        assert match is not None
        assert match["acknowledged_by_name"] == "Max Mustermann"

    def test_ack_without_name_backward_compat_returns_null(self, incident_id, resource):
        evt = _create_alert_event(incident_id, resource["id"])
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "fuehrungsassistenz"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["acknowledged_by_role"] == "fuehrungsassistenz"
        # name not provided -> must be None (not missing)
        assert body.get("acknowledged_by_name") is None

    def test_ack_with_whitespace_only_name_is_normalized_to_null(self, incident_id, resource):
        evt = _create_alert_event(incident_id, resource["id"])
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "einsatzleiter", "name": "   "},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("acknowledged_by_name") is None

    def test_ack_with_name_too_long_returns_422(self, incident_id, resource):
        evt = _create_alert_event(incident_id, resource["id"])
        long_name = "A" * 121
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "einsatzleiter", "name": long_name},
            timeout=10,
        )
        assert r.status_code == 422, r.text

    def test_ack_with_name_exactly_120_chars_ok(self, incident_id, resource):
        evt = _create_alert_event(incident_id, resource["id"])
        name = "B" * 120
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "einsatzleiter", "name": name},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json()["acknowledged_by_name"] == name

    def test_ack_with_helfer_role_still_403_even_with_name(self, incident_id, resource):
        evt = _create_alert_event(incident_id, resource["id"])
        r = requests.post(
            f"{API}/fms-events/{evt['id']}/acknowledge",
            json={"role": "helfer", "name": "Test User"},
            timeout=10,
        )
        assert r.status_code == 403, r.text
