"""Tests for FMS-Audit-Trail (fms_events collection + GET /api/incidents/{id}/fms-events).

Covers:
- Manual PATCH /api/resources/{id} with fms_status creates event with source='manual'
- PATCH with unchanged fms_status does NOT create event (no-change skip)
- PATCH without fms_status field does not trigger audit
- Resource linked to divera_id does NOT log via manual PATCH (Divera path logs separately)
- GET /api/incidents/{id}/fms-events returns events sorted ts DESC
- Query params resource_id (filter) and limit (1..1000, default 200)
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to backend/.env (testing inside container)
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
    payload = {
        "name": f"TEST_FMS_AUDIT_{uuid.uuid4().hex[:6]}",
        "meldebild": "test",
    }
    r = requests.post(f"{API}/incidents", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    inc = r.json()
    yield inc["id"]
    # Cleanup
    try:
        requests.delete(f"{API}/incidents/{inc['id']}", timeout=10)
    except Exception:
        pass


@pytest.fixture
def resource(incident_id):
    payload = {"name": "TEST_FMS_VEH", "typ": "intern", "kategorie": "rtw"}
    r = requests.post(f"{API}/incidents/{incident_id}/resources", json=payload, timeout=10)
    assert r.status_code == 201, r.text
    res = r.json()
    yield res
    try:
        requests.delete(f"{API}/resources/{res['id']}", timeout=10)
    except Exception:
        pass


@pytest.fixture
def linked_resource(incident_id):
    """Resource WITH divera_id — manual PATCH should NOT create audit event."""
    payload = {
        "name": "TEST_FMS_DIVERA",
        "typ": "intern",
        "kategorie": "rtw",
        "divera_id": "999999",
    }
    r = requests.post(f"{API}/incidents/{incident_id}/resources", json=payload, timeout=10)
    assert r.status_code == 201
    res = r.json()
    yield res
    try:
        requests.delete(f"{API}/resources/{res['id']}", timeout=10)
    except Exception:
        pass


# ---------- GET endpoint sanity ----------
class TestFmsEventsEndpoint:
    def test_endpoint_returns_array_when_empty(self, incident_id):
        r = requests.get(f"{API}/incidents/{incident_id}/fms-events", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_limit_clamped(self, incident_id):
        # limit=0 should be clamped to 1
        r = requests.get(f"{API}/incidents/{incident_id}/fms-events?limit=0", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_resource_id_filter(self, incident_id, resource):
        rid = resource["id"]
        # create one event
        requests.patch(f"{API}/resources/{rid}", json={"fms_status": 1}, timeout=10)
        # filter by an OTHER id → must be empty
        other = uuid.uuid4().hex
        r = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": other},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json() == []
        # filter by THIS id → at least 1
        r2 = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": rid},
            timeout=10,
        )
        assert r2.status_code == 200
        assert len(r2.json()) >= 1


# ---------- Manual PATCH audit ----------
class TestManualPatchAudit:
    def test_patch_fms_creates_manual_event(self, incident_id, resource):
        rid = resource["id"]
        # baseline events
        before = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": rid},
            timeout=10,
        ).json()
        before_count = len(before)

        r = requests.patch(f"{API}/resources/{rid}", json={"fms_status": 4}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("fms_status") == 4

        after = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": rid},
            timeout=10,
        ).json()
        assert len(after) == before_count + 1
        evt = after[0]  # sorted DESC
        # field validation
        for k in (
            "id",
            "incident_id",
            "resource_id",
            "resource_name",
            "from_fms",
            "to_fms",
            "from_status",
            "to_status",
            "source",
            "ts",
        ):
            assert k in evt, f"missing field {k}"
        assert evt["source"] == "manual"
        assert evt["to_fms"] == 4
        assert evt["resource_id"] == rid
        assert evt["incident_id"] == incident_id

    def test_patch_unchanged_fms_no_event(self, incident_id, resource):
        rid = resource["id"]
        # set to 1
        requests.patch(f"{API}/resources/{rid}", json={"fms_status": 1}, timeout=10)
        baseline = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": rid},
            timeout=10,
        ).json()
        baseline_count = len(baseline)
        # patch same value
        r = requests.patch(f"{API}/resources/{rid}", json={"fms_status": 1}, timeout=10)
        assert r.status_code == 200
        after = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": rid},
            timeout=10,
        ).json()
        assert len(after) == baseline_count, "no-change PATCH must NOT create event"

    def test_patch_without_fms_field_no_event(self, incident_id, resource):
        rid = resource["id"]
        baseline = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": rid},
            timeout=10,
        ).json()
        baseline_count = len(baseline)
        r = requests.patch(f"{API}/resources/{rid}", json={"notiz": "test"}, timeout=10)
        assert r.status_code == 200
        after = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": rid},
            timeout=10,
        ).json()
        assert len(after) == baseline_count

    def test_three_fms_changes_create_three_events_desc_order(self, incident_id, resource):
        rid = resource["id"]
        # reset baseline by querying current
        baseline_count = len(
            requests.get(
                f"{API}/incidents/{incident_id}/fms-events",
                params={"resource_id": rid},
                timeout=10,
            ).json()
        )
        for fms in (2, 3, 6):
            r = requests.patch(f"{API}/resources/{rid}", json={"fms_status": fms}, timeout=10)
            assert r.status_code == 200
            time.sleep(0.05)
        events = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": rid},
            timeout=10,
        ).json()
        assert len(events) == baseline_count + 3
        # newest first → first event has to_fms == 6
        assert events[0]["to_fms"] == 6
        # ts descending
        ts_list = [e["ts"] for e in events]
        assert ts_list == sorted(ts_list, reverse=True)


# ---------- Linked-resource skip ----------
class TestLinkedResourceSkip:
    def test_manual_patch_on_linked_resource_no_manual_event(self, incident_id, linked_resource):
        rid = linked_resource["id"]
        # send a manual patch — since resource has divera_id, server must NOT log via manual path
        r = requests.patch(f"{API}/resources/{rid}", json={"fms_status": 5}, timeout=10)
        assert r.status_code == 200
        events = requests.get(
            f"{API}/incidents/{incident_id}/fms-events",
            params={"resource_id": rid},
            timeout=10,
        ).json()
        assert events == [], (
            "Resources WITH divera_id must NOT generate 'manual' audit events on PATCH"
        )
