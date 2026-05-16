"""
Iter 24: Backend tests for the new Abschnitt-Delete rule.

Rule (new):
- Loeschen erlaubt sobald keine Betten am Abschnitt belegt sind, unabhaengig
  vom Incident-Status (aktiv/geplant/abgeschlossen).
- 204 bei keinen belegten Betten. Verbliebene freie/gesperrte Betten und
  Resources werden auf abschnitt_id=null entkoppelt.
- 409 mit konkretem Detail bei >=1 belegtem Bett.
- 404 bei unbekannter Abschnitt-id.
"""

import os
import pytest
import requests
from pathlib import Path


def _load_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if url:
        return url.rstrip("/")
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    return ""


BASE_URL = _load_url()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"


@pytest.fixture()
def incident():
    """Fresh active incident per test (for isolation)."""
    r = requests.post(
        f"{API}/incidents",
        json={"name": "TEST_AbschDelRule", "typ": "uebung", "ort": "Testhalle"},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    inc = r.json()
    yield inc
    try:
        requests.delete(f"{API}/incidents/{inc['id']}", timeout=10)
    except Exception:
        pass


class TestAbschnittDeleteRule:
    # 204 wenn Abschnitt komplett leer (keine Betten/Resources)
    def test_delete_empty_active_incident_returns_204(self, incident):
        inc_id = incident["id"]
        r = requests.post(
            f"{API}/incidents/{inc_id}/abschnitte",
            json={"name": "TEST_LeerLeer", "farbe": "blue"},
            timeout=10,
        )
        assert r.status_code == 201
        aid = r.json()["id"]
        # Incident is aktiv: old rule was 409, new rule must be 204.
        d = requests.delete(f"{API}/abschnitte/{aid}", timeout=10)
        assert d.status_code == 204, f"expected 204, got {d.status_code}: {d.text}"
        # confirm gone
        g = requests.get(f"{API}/abschnitte/{aid}", timeout=10)
        assert g.status_code == 404

    # 204 wenn Abschnitt nur freie/gesperrte Betten hat -> Betten werden entkoppelt
    def test_delete_with_only_free_and_sperr_betten_unlinks_and_204(self, incident):
        inc_id = incident["id"]
        a = requests.post(
            f"{API}/incidents/{inc_id}/abschnitte",
            json={"name": "TEST_NurFrei"},
            timeout=10,
        ).json()
        aid = a["id"]
        # Create two beds in abschnitt: 1 frei, 1 gesperrt (via patch)
        b1 = requests.post(
            f"{API}/incidents/{inc_id}/betten",
            json={"name": "TEST_F1", "abschnitt_id": aid, "typ": "liegend"},
            timeout=10,
        ).json()
        b2 = requests.post(
            f"{API}/incidents/{inc_id}/betten",
            json={"name": "TEST_F2", "abschnitt_id": aid, "typ": "liegend"},
            timeout=10,
        ).json()
        # mark b2 as gesperrt
        pr = requests.patch(f"{API}/betten/{b2['id']}", json={"status": "gesperrt"}, timeout=10)
        assert pr.status_code == 200

        d = requests.delete(f"{API}/abschnitte/{aid}", timeout=10)
        assert d.status_code == 204, d.text

        # Both beds remain but with abschnitt_id=null
        for bid in (b1["id"], b2["id"]):
            gb = requests.get(f"{API}/betten/{bid}", timeout=10)
            assert gb.status_code == 200, gb.text
            body = gb.json()
            assert body.get("abschnitt_id") in (None, ""), body

    # 409 wenn >=1 Bett des Abschnitts 'belegt'
    def test_delete_with_belegtes_bett_returns_409(self, incident):
        inc_id = incident["id"]
        a = requests.post(
            f"{API}/incidents/{inc_id}/abschnitte",
            json={"name": "TEST_HasBelegt"},
            timeout=10,
        ).json()
        aid = a["id"]
        # patient + bett + assign
        p = requests.post(
            f"{API}/incidents/{inc_id}/patients",
            json={"kennung": "TEST_PAT_D", "sichtung": "S2", "status": "in_behandlung"},
            timeout=10,
        ).json()
        b = requests.post(
            f"{API}/incidents/{inc_id}/betten",
            json={"name": "TEST_Belegt1", "abschnitt_id": aid},
            timeout=10,
        ).json()
        ar = requests.post(f"{API}/betten/{b['id']}/assign", json={"patient_id": p["id"]}, timeout=10)
        assert ar.status_code == 200, ar.text
        assert ar.json()["status"] == "belegt"

        d = requests.delete(f"{API}/abschnitte/{aid}", timeout=10)
        assert d.status_code == 409, d.text
        detail = d.json().get("detail", "")
        assert "Abschnitt nicht loeschbar" in detail, detail
        assert "1 Bett" in detail, detail
        # abschnitt still exists
        g = requests.get(f"{API}/abschnitte/{aid}", timeout=10)
        assert g.status_code == 200

        # release -> dann 204
        rr = requests.post(f"{API}/betten/{b['id']}/release", timeout=10)
        assert rr.status_code == 200
        d2 = requests.delete(f"{API}/abschnitte/{aid}", timeout=10)
        assert d2.status_code == 204, d2.text

    # 404 fuer unbekannten Abschnitt
    def test_delete_unknown_returns_404(self):
        d = requests.delete(f"{API}/abschnitte/does-not-exist-xyz-999", timeout=10)
        assert d.status_code == 404
