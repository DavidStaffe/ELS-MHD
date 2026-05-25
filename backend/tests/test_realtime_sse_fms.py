"""Iteration 20 — Realtime SSE + Auto-Position tests.

Validates:
- GET /api/incidents/stream emits 'event: incident' with kind='fms_event' when a
  resource's fms_status is patched to 5/0 (is_alert=True) or 3 (is_alert=False).
- Divera-Auto-Position: services/divera.py.sync_incident writes lat/lng if Divera
  delivers them and they differ — 0/0 is ignored as 'no fix'.
"""
import json
import os
import threading
import time
import uuid
from typing import List, Optional

import pytest
import requests


def _load_backend_url():
    val = os.environ.get("REACT_APP_BACKEND_URL")
    if val:
        return val
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return ""


BASE_URL = _load_backend_url().rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def incident_id(http):
    r = http.get(f"{API}/incidents")
    r.raise_for_status()
    items = r.json()
    assert items, "No incidents in DB"
    # prefer demo incident MANV-Uebung Sued (active)
    active = [i for i in items if i.get("status") != "abgeschlossen"]
    return (active[0] if active else items[0])["id"]


@pytest.fixture(scope="module")
def resource_id(http, incident_id):
    r = http.get(f"{API}/incidents/{incident_id}/resources")
    r.raise_for_status()
    resources = r.json()
    # Prefer a resource WITHOUT divera_id so manual fms_status PATCH triggers
    # record_fms_change (route skips audit when divera_id linked).
    cand = [x for x in resources if not x.get("divera_id")]
    assert cand, "No unlinked resources to test manual FMS change"
    return cand[0]["id"]


# ---------------- SSE helper ----------------

class SSECollector:
    """Background SSE reader. Collects 'event: incident' payloads."""

    def __init__(self, url: str, timeout: float = 8.0):
        self.url = url
        self.timeout = timeout
        self.events: List[dict] = []
        self._stop = False
        self._thread: Optional[threading.Thread] = None
        self.ready = threading.Event()

    def _run(self):
        try:
            with requests.get(
                self.url,
                stream=True,
                headers={"Accept": "text/event-stream"},
                timeout=self.timeout,
            ) as resp:
                self.ready.set()
                evt_type = None
                data_lines: List[str] = []
                start = time.time()
                for raw in resp.iter_lines(decode_unicode=True):
                    if self._stop or time.time() - start > self.timeout:
                        break
                    if raw is None:
                        continue
                    line = raw.strip("\r")
                    if line == "":
                        if evt_type == "incident" and data_lines:
                            try:
                                self.events.append(json.loads("\n".join(data_lines)))
                            except Exception:
                                pass
                        evt_type = None
                        data_lines = []
                        continue
                    if line.startswith("event:"):
                        evt_type = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line.split(":", 1)[1].lstrip())
        except Exception:
            self.ready.set()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.ready.wait(timeout=3)

    def stop(self):
        self._stop = True
        if self._thread:
            self._thread.join(timeout=1)

    def wait_for(self, predicate, timeout=6.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for ev in self.events:
                if predicate(ev):
                    return ev
            time.sleep(0.15)
        return None


# ---------------- Tests ----------------

class TestSSEFmsEvent:
    """Realtime FMS event push via /api/incidents/stream."""

    def _patch_fms(self, http, resource_id, value):
        return http.patch(
            f"{API}/resources/{resource_id}", json={"fms_status": value}
        )

    def test_stream_emits_alert_for_fms5(self, http, resource_id, incident_id):
        # ensure baseline is not 5 already
        r = http.patch(f"{API}/resources/{resource_id}", json={"fms_status": 2})
        assert r.status_code == 200
        time.sleep(0.3)

        collector = SSECollector(f"{API}/incidents/stream", timeout=8.0)
        collector.start()
        time.sleep(0.5)  # let connection establish

        r = self._patch_fms(http, resource_id, 5)
        assert r.status_code == 200, r.text

        ev = collector.wait_for(
            lambda e: e.get("kind") == "fms_event"
            and e.get("incident_id") == incident_id
            and (e.get("event") or {}).get("to_fms") == 5,
            timeout=6,
        )
        collector.stop()
        assert ev is not None, f"No SSE fms_event(5) received; got: {collector.events[:5]}"
        assert ev.get("is_alert") is True
        assert ev.get("event", {}).get("to_fms") == 5
        assert ev.get("event", {}).get("resource_id") == resource_id

    def test_stream_no_alert_for_fms3(self, http, resource_id, incident_id):
        # reset to 5 so transition 5->3 will be recorded
        r = http.patch(f"{API}/resources/{resource_id}", json={"fms_status": 5})
        assert r.status_code == 200
        time.sleep(0.3)

        collector = SSECollector(f"{API}/incidents/stream", timeout=8.0)
        collector.start()
        time.sleep(0.5)

        r = self._patch_fms(http, resource_id, 3)
        assert r.status_code == 200, r.text

        ev = collector.wait_for(
            lambda e: e.get("kind") == "fms_event"
            and e.get("incident_id") == incident_id
            and (e.get("event") or {}).get("to_fms") == 3,
            timeout=6,
        )
        collector.stop()
        assert ev is not None, f"No SSE fms_event(3) received; got: {collector.events[:5]}"
        assert ev.get("is_alert") is False


# ---------------- Auto-Position (Divera Sync) ----------------

class TestDiveraAutoPosition:
    """Verify sync_incident updates lat/lng but rejects 0/0."""

    def test_sync_updates_resource_lat_lng_from_divera(self, http, incident_id):
        """Run sync_incident in a single fresh event loop with a fresh motor client."""
        import asyncio
        import sys
        sys.path.insert(0, "/app/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from services import divera as divera_module
        import core.db as core_db

        new_lat, new_lng = 52.5200, 13.4050  # Berlin

        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            local_db = client[os.environ["DB_NAME"]]
            # Swap global db used by divera_module/fms_audit
            original_db = core_db.db
            core_db.db = local_db
            # Also patch module-level imported bindings (`from core.db import db`)
            from services import fms_audit as fms_audit_module
            from services import realtime as realtime_module
            original_div_db = divera_module.db
            original_aud_db = fms_audit_module.db
            divera_module.db = local_db
            fms_audit_module.db = local_db
            if hasattr(realtime_module, "db"):
                realtime_module.db = local_db

            try:
                linked = await local_db.resources.find_one(
                    {"incident_id": incident_id, "divera_id": {"$nin": [None, ""]}},
                    {"_id": 0},
                )
                if not linked:
                    res = await local_db.resources.find_one(
                        {"incident_id": incident_id}, {"_id": 0}
                    )
                    assert res, "No resource to link"
                    await local_db.resources.update_one(
                        {"id": res["id"]}, {"$set": {"divera_id": "TEST_VEHICLE"}}
                    )
                    linked = await local_db.resources.find_one(
                        {"id": res["id"]}, {"_id": 0}
                    )
                rid = linked["id"]
                divera_id = str(linked["divera_id"])

                original_fetch = divera_module.fetch_vehicles

                async def fake_fetch(api_key=None):
                    return [
                        {
                            "id": int(divera_id) if divera_id.isdigit() else divera_id,
                            "name": "TestVeh",
                            "fmsstatus": 2,
                            "lat": new_lat,
                            "lng": new_lng,
                        }
                    ]

                divera_module.fetch_vehicles = fake_fetch
                try:
                    result = await divera_module.sync_incident(incident_id)
                    assert result.get("ok"), result
                    after = await local_db.resources.find_one({"id": rid}, {"_id": 0})
                    return after
                finally:
                    divera_module.fetch_vehicles = original_fetch
            finally:
                core_db.db = original_db
                divera_module.db = original_div_db
                fms_audit_module.db = original_aud_db
                client.close()

        updated = asyncio.run(_run())
        assert updated is not None
        assert updated.get("lat") == pytest.approx(new_lat, abs=1e-6)
        assert updated.get("lng") == pytest.approx(new_lng, abs=1e-6)

    def test_sync_ignores_zero_zero(self, http, incident_id):
        import asyncio
        import sys
        sys.path.insert(0, "/app/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from services import divera as divera_module
        from services import fms_audit as fms_audit_module
        import core.db as core_db

        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            local_db = client[os.environ["DB_NAME"]]
            original_db = core_db.db
            core_db.db = local_db
            original_div_db = divera_module.db
            original_aud_db = fms_audit_module.db
            divera_module.db = local_db
            fms_audit_module.db = local_db
            try:
                linked = await local_db.resources.find_one(
                    {"incident_id": incident_id, "divera_id": {"$nin": [None, ""]}},
                    {"_id": 0},
                )
                assert linked, "Need a linked resource"
                rid = linked["id"]
                divera_id = str(linked["divera_id"])
                # Baseline
                await local_db.resources.update_one(
                    {"id": rid}, {"$set": {"lat": 10.0, "lng": 10.0}}
                )

                original_fetch = divera_module.fetch_vehicles

                async def fake_fetch(api_key=None):
                    return [
                        {
                            "id": int(divera_id) if divera_id.isdigit() else divera_id,
                            "name": "ZeroFix",
                            "fmsstatus": 2,
                            "lat": 0,
                            "lng": 0,
                        }
                    ]

                divera_module.fetch_vehicles = fake_fetch
                try:
                    await divera_module.sync_incident(incident_id)
                    return await local_db.resources.find_one({"id": rid}, {"_id": 0})
                finally:
                    divera_module.fetch_vehicles = original_fetch
            finally:
                core_db.db = original_db
                divera_module.db = original_div_db
                fms_audit_module.db = original_aud_db
                client.close()

        updated = asyncio.run(_run())
        assert updated.get("lat") == pytest.approx(10.0, abs=1e-6)
        assert updated.get("lng") == pytest.approx(10.0, abs=1e-6)
