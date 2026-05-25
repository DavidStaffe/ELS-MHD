"""Tests for FMS-Quittierung mit Revert + 'SPRECHEN SIE' an Divera.

Covers (iteration 21):
- acknowledge_fms_event sets reverted_to_fms / revert_sent_to_divera correctly
  depending on from_fms, divera_id, Divera reachability.
- Local resource is reset to previous fms_status even if Divera-call fails.
- SSE-publish of kind='resource', action='fms_reverted' after ack with revert.
- services.divera.set_vehicle_status performs correct GET /api/fms call and
  raises ValueError on success=false.
- Regression: existing ack rules (helfer 403, double 409, non-alert 409,
  unknown 404) still green.
"""
import asyncio
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import requests
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
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

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client[DB_NAME]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def incident_id():
    payload = {"name": f"TEST_FMS_REVERT_{uuid.uuid4().hex[:6]}", "meldebild": "revert test"}
    r = requests.post(f"{API}/incidents", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    inc = r.json()
    yield inc["id"]
    try:
        requests.delete(f"{API}/incidents/{inc['id']}", timeout=10)
    except Exception:
        pass


def _make_resource(incident_id: str, divera_id: Optional[str] = None,
                   initial_fms: Optional[int] = None,
                   initial_status: Optional[str] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {"name": f"TEST_REV_{uuid.uuid4().hex[:4]}", "typ": "intern", "kategorie": "rtw"}
    if divera_id:
        body["divera_id"] = divera_id
    r = requests.post(f"{API}/incidents/{incident_id}/resources", json=body, timeout=10)
    assert r.status_code == 201, r.text
    res = r.json()
    upd: Dict[str, Any] = {}
    if initial_fms is not None:
        upd["fms_status"] = initial_fms
    if initial_status is not None:
        upd["status"] = initial_status
    if upd:
        # Update via direct Mongo to avoid triggering audit
        mongo_db.resources.update_one({"id": res["id"]}, {"$set": upd})
        res.update(upd)
    return res


def _seed_event(*, incident_id: str, resource_id: str, resource_name: str,
                from_fms: Optional[int], to_fms: int = 5,
                divera_id: Optional[str] = None,
                is_alert: bool = True) -> Dict[str, Any]:
    """Insert an fms_event directly so we can choose divera_id + from_fms freely."""
    doc = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "vehicle_name": None,
        "divera_id": divera_id,
        "from_fms": from_fms,
        "to_fms": to_fms,
        "from_status": "im_einsatz" if from_fms in (3, 4, 7, 8) else None,
        "to_status": None,
        "source": "divera" if divera_id else "manual",
        "ts": "2026-01-15T10:00:00+00:00",
        "is_alert": is_alert,
        "acknowledged_by_role": None,
        "acknowledged_at": None,
    }
    mongo_db.fms_events.insert_one(doc)
    # remove _id-mutating object so we don't accidentally use it later
    doc.pop("_id", None)
    return doc


def _cleanup_event(event_id: str):
    try:
        mongo_db.fms_events.delete_one({"id": event_id})
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1) HTTP-Level: acknowledge_fms_event Revert-Logic
# ---------------------------------------------------------------------------
class TestRevertViaAcknowledgeEndpoint:
    def test_from_fms_4_with_divera_id_sets_revert_and_resource(self, incident_id):
        """from_fms=4 + divera_id → revert_target=4 set, local resource reset.

        Divera-Call will fail (DNS unreachable in unit-env) → revert_sent_to_divera=False
        is acceptable; we assert the local revert + reverted_to_fms in any case.
        """
        res = _make_resource(incident_id, divera_id="DV-TEST-001",
                             initial_fms=5, initial_status="sprechwunsch")
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=4, to_fms=5,
                          divera_id="DV-TEST-001")
        try:
            r = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=15,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["acknowledged_by_role"] == "einsatzleiter"
            assert body["reverted_to_fms"] == 4
            # divera_sent may be true or false depending on Divera reachability;
            # but if false there must be an error string
            assert "revert_sent_to_divera" in body
            if body["revert_sent_to_divera"] is False:
                assert body.get("revert_divera_error"), body
            # Local resource updated
            res_doc = mongo_db.resources.find_one({"id": res["id"]}, {"_id": 0})
            assert res_doc["fms_status"] == 4
            assert res_doc["status"] == "im_einsatz"
        finally:
            _cleanup_event(evt["id"])

    def test_from_fms_null_no_revert_target(self, incident_id):
        """from_fms=None → reverted_to_fms=None, no divera call, resource unchanged."""
        res = _make_resource(incident_id, initial_fms=5, initial_status="sprechwunsch")
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=None, to_fms=5)
        try:
            r = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=10,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["acknowledged_by_role"] == "einsatzleiter"
            assert body.get("reverted_to_fms") is None
            assert body.get("revert_sent_to_divera") is False
            # Resource fms_status unchanged
            res_doc = mongo_db.resources.find_one({"id": res["id"]}, {"_id": 0})
            assert res_doc["fms_status"] == 5  # unchanged
        finally:
            _cleanup_event(evt["id"])

    def test_from_fms_alert_code_no_revert(self, incident_id):
        """from_fms=0 (also alert) → revert NOT into alert-code, stays None."""
        res = _make_resource(incident_id, initial_fms=5, initial_status="sprechwunsch")
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=0, to_fms=5)
        try:
            r = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=10,
            )
            assert r.status_code == 200, r.text
            assert r.json().get("reverted_to_fms") is None
        finally:
            _cleanup_event(evt["id"])

    def test_from_fms_4_without_divera_id_local_revert_only(self, incident_id):
        """from_fms=4 + divera_id=None → revert local only, no Divera-Push."""
        res = _make_resource(incident_id, initial_fms=5, initial_status="sprechwunsch")
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=4, to_fms=5,
                          divera_id=None)
        try:
            r = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=10,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["reverted_to_fms"] == 4
            assert body["revert_sent_to_divera"] is False
            assert body.get("revert_divera_error") in (None, "")
            res_doc = mongo_db.resources.find_one({"id": res["id"]}, {"_id": 0})
            assert res_doc["fms_status"] == 4
            assert res_doc["status"] == "im_einsatz"
        finally:
            _cleanup_event(evt["id"])

    def test_from_fms_2_verfuegbar_revert_to_status_verfuegbar(self, incident_id):
        """from_fms=2 → reverted to verfuegbar local status."""
        res = _make_resource(incident_id, initial_fms=5, initial_status="sprechwunsch")
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=2, to_fms=5)
        try:
            r = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=10,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["reverted_to_fms"] == 2
            res_doc = mongo_db.resources.find_one({"id": res["id"]}, {"_id": 0})
            assert res_doc["fms_status"] == 2
            assert res_doc["status"] == "verfuegbar"
        finally:
            _cleanup_event(evt["id"])

    # ------------------------------------------------------------------
    # Regression: existing ack rules
    # ------------------------------------------------------------------
    def test_ack_unknown_event_returns_404(self):
        r = requests.post(
            f"{API}/fms-events/{uuid.uuid4().hex}/acknowledge",
            json={"role": "einsatzleiter"}, timeout=10,
        )
        assert r.status_code == 404, r.text

    def test_ack_helfer_returns_403(self, incident_id):
        res = _make_resource(incident_id, initial_fms=5)
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=4, to_fms=5)
        try:
            r = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "helfer"}, timeout=10,
            )
            assert r.status_code == 403, r.text
        finally:
            _cleanup_event(evt["id"])

    def test_double_ack_returns_409(self, incident_id):
        res = _make_resource(incident_id, initial_fms=5)
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=4, to_fms=5)
        try:
            r1 = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=10,
            )
            assert r1.status_code == 200, r1.text
            r2 = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=10,
            )
            assert r2.status_code == 409, r2.text
        finally:
            _cleanup_event(evt["id"])

    def test_non_alert_event_returns_409(self, incident_id):
        res = _make_resource(incident_id, initial_fms=2)
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=2, to_fms=3,
                          is_alert=False)
        try:
            r = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=10,
            )
            assert r.status_code == 409, r.text
        finally:
            _cleanup_event(evt["id"])


# ---------------------------------------------------------------------------
# 2) Verlauf-Endpoint enthaelt neue Felder
# ---------------------------------------------------------------------------
class TestFmsEventsListExposesRevertFields:
    def test_listing_after_ack_contains_revert_fields(self, incident_id):
        res = _make_resource(incident_id, initial_fms=5, initial_status="sprechwunsch")
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=4, to_fms=5)
        try:
            r = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=10,
            )
            assert r.status_code == 200
            events = requests.get(
                f"{API}/incidents/{incident_id}/fms-events",
                params={"resource_id": res["id"]}, timeout=10,
            ).json()
            match = next((e for e in events if e["id"] == evt["id"]), None)
            assert match is not None
            assert match.get("reverted_to_fms") == 4
            assert "revert_sent_to_divera" in match
        finally:
            _cleanup_event(evt["id"])


# ---------------------------------------------------------------------------
# 3) SSE: action='fms_reverted' wird publisht
# ---------------------------------------------------------------------------
class TestSseFmsRevertedEvent:
    def test_sse_resource_fms_reverted_after_ack(self, incident_id):
        res = _make_resource(incident_id, initial_fms=5, initial_status="sprechwunsch")
        evt = _seed_event(incident_id=incident_id, resource_id=res["id"],
                          resource_name=res["name"], from_fms=4, to_fms=5)
        captured: List[Dict[str, Any]] = []

        def consume_sse():
            # Read up to 4 seconds of SSE data
            with requests.get(f"{API}/incidents/stream", stream=True, timeout=8) as resp:
                start = time.time()
                buf = ""
                for line in resp.iter_lines(decode_unicode=True):
                    if line is None:
                        continue
                    if line.startswith("data:"):
                        try:
                            payload = json.loads(line[5:].strip())
                            captured.append(payload)
                        except Exception:
                            pass
                    if time.time() - start > 4:
                        break

        import threading
        t = threading.Thread(target=consume_sse, daemon=True)
        t.start()
        # let SSE connect
        time.sleep(0.7)
        try:
            r = requests.post(
                f"{API}/fms-events/{evt['id']}/acknowledge",
                json={"role": "einsatzleiter"}, timeout=10,
            )
            assert r.status_code == 200, r.text
            t.join(timeout=6)
            matches = [
                p for p in captured
                if p.get("kind") == "resource"
                and p.get("action") == "fms_reverted"
                and p.get("resource_id") == res["id"]
            ]
            assert matches, f"expected fms_reverted SSE, got: {captured[-10:]}"
            assert matches[0].get("fms_status") == 4
        finally:
            _cleanup_event(evt["id"])


# ---------------------------------------------------------------------------
# 4) services.divera.set_vehicle_status (httpx mock)
# ---------------------------------------------------------------------------
class _FakeResp:
    def __init__(self, status_code: int, payload: Dict[str, Any]):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Captures the GET URL + params and returns a configurable JSON payload."""
    last_url: Optional[str] = None
    last_params: Optional[Dict[str, Any]] = None
    response_payload: Dict[str, Any] = {"success": True}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        _FakeAsyncClient.last_url = url
        _FakeAsyncClient.last_params = params
        return _FakeResp(200, _FakeAsyncClient.response_payload)


class TestSetVehicleStatusUnit:
    def test_set_vehicle_status_calls_fms_endpoint(self, monkeypatch):
        """set_vehicle_status() must GET /api/fms with proper params + status_note."""
        import sys
        sys.path.insert(0, "/app/backend")
        from services import divera as divera_module

        monkeypatch.setattr(divera_module, "DIVERA_API_KEY", "DUMMYKEY")
        monkeypatch.setattr(divera_module, "DIVERA_BASE_URL", "https://divera247.com")
        monkeypatch.setattr(divera_module.httpx, "AsyncClient", _FakeAsyncClient)
        _FakeAsyncClient.last_url = None
        _FakeAsyncClient.last_params = None
        _FakeAsyncClient.response_payload = {"success": True}

        result = asyncio.run(divera_module.set_vehicle_status(
            divera_id="V123", status_id=4, status_note="SPRECHEN SIE",
        ))
        assert _FakeAsyncClient.last_url == "https://divera247.com/api/fms"
        p = _FakeAsyncClient.last_params or {}
        assert p.get("accesskey") == "DUMMYKEY"
        assert str(p.get("vehicle_id")) == "V123"
        assert int(p.get("status_id")) == 4
        assert p.get("status_note") == "SPRECHEN SIE"
        assert result.get("success") is True

    def test_set_vehicle_status_raises_on_success_false(self, monkeypatch):
        import sys
        sys.path.insert(0, "/app/backend")
        from services import divera as divera_module

        monkeypatch.setattr(divera_module, "DIVERA_API_KEY", "DUMMYKEY")
        monkeypatch.setattr(divera_module.httpx, "AsyncClient", _FakeAsyncClient)
        _FakeAsyncClient.response_payload = {"success": False, "message": "Invalid vehicle"}

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(divera_module.set_vehicle_status(
                divera_id="V123", status_id=4, status_note="SPRECHEN SIE",
            ))
        assert "Invalid vehicle" in str(exc_info.value)

    def test_set_vehicle_status_missing_divera_id_raises(self, monkeypatch):
        import sys
        sys.path.insert(0, "/app/backend")
        from services import divera as divera_module

        monkeypatch.setattr(divera_module, "DIVERA_API_KEY", "DUMMYKEY")
        with pytest.raises(ValueError):
            asyncio.run(divera_module.set_vehicle_status(
                divera_id="", status_id=4,
            ))
