"""Phase 2 tests: Abschnitt polygon field (create/patch/clear/list)."""
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


BASE = _load_url()
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def incident_id():
    # Create a fresh test incident
    r = requests.post(f"{API}/incidents", json={
        "name": "TEST_PHASE2_POLYGON",
        "typ": "veranstaltung",
        "ort": "Hamburg",
        "ort_lat": 53.5511,
        "ort_lng": 9.9937,
        "ort_zoom": 14,
    })
    assert r.status_code in (200, 201), r.text
    inc = r.json()
    yield inc["id"]
    # cleanup: best-effort delete
    requests.delete(f"{API}/incidents/{inc['id']}")


# --- Polygon create flow ---------------------------------------------------

def test_create_abschnitt_without_polygon_returns_null(incident_id):
    r = requests.post(f"{API}/incidents/{incident_id}/abschnitte", json={
        "name": "TEST_EA_NoPoly", "farbe": "blue"
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert "polygon" in data
    assert data["polygon"] is None


def test_create_abschnitt_with_polygon(incident_id):
    poly = [[53.55, 9.99], [53.56, 9.99], [53.555, 10.00]]
    r = requests.post(f"{API}/incidents/{incident_id}/abschnitte", json={
        "name": "TEST_EA_WithPoly", "farbe": "red", "polygon": poly
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["polygon"] == poly
    # Verify GET persistence
    aid = data["id"]
    r2 = requests.get(f"{API}/abschnitte/{aid}")
    assert r2.status_code == 200
    assert r2.json()["polygon"] == poly


def test_patch_abschnitt_set_polygon(incident_id):
    # create without polygon
    r = requests.post(f"{API}/incidents/{incident_id}/abschnitte",
                      json={"name": "TEST_EA_SetPoly", "farbe": "green"})
    aid = r.json()["id"]
    poly = [[53.5, 9.9], [53.51, 9.92], [53.49, 9.93], [53.495, 9.91]]
    r2 = requests.patch(f"{API}/abschnitte/{aid}", json={"polygon": poly})
    assert r2.status_code == 200, r2.text
    assert r2.json()["polygon"] == poly
    # GET to confirm persistence
    r3 = requests.get(f"{API}/abschnitte/{aid}")
    assert r3.json()["polygon"] == poly


def test_patch_polygon_null_clears(incident_id):
    poly = [[53.5, 9.9], [53.51, 9.92], [53.49, 9.93]]
    r = requests.post(f"{API}/incidents/{incident_id}/abschnitte",
                      json={"name": "TEST_EA_Clear", "farbe": "orange",
                            "polygon": poly})
    aid = r.json()["id"]
    # Now PATCH with polygon=null
    r2 = requests.patch(f"{API}/abschnitte/{aid}", json={"polygon": None})
    assert r2.status_code == 200, r2.text
    assert r2.json()["polygon"] is None
    # Confirm persisted
    assert requests.get(f"{API}/abschnitte/{aid}").json()["polygon"] is None


def test_patch_low_point_polygon_accepted_by_server(incident_id):
    """Server should accept low-point polygon (FE enforces >=3 points)."""
    r = requests.post(f"{API}/incidents/{incident_id}/abschnitte",
                      json={"name": "TEST_EA_LowPt", "farbe": "purple"})
    aid = r.json()["id"]
    # 1 point - server should still accept (FE-side validation)
    r2 = requests.patch(f"{API}/abschnitte/{aid}",
                        json={"polygon": [[53.5, 9.9]]})
    assert r2.status_code == 200, r2.text
    assert r2.json()["polygon"] == [[53.5, 9.9]]


def test_list_abschnitte_includes_polygon(incident_id):
    poly = [[53.6, 9.8], [53.61, 9.82], [53.59, 9.83]]
    r = requests.post(f"{API}/incidents/{incident_id}/abschnitte",
                      json={"name": "TEST_EA_List", "farbe": "yellow",
                            "polygon": poly})
    aid = r.json()["id"]
    r2 = requests.get(f"{API}/incidents/{incident_id}/abschnitte")
    assert r2.status_code == 200
    rows = r2.json()
    found = [a for a in rows if a["id"] == aid]
    assert len(found) == 1
    assert found[0]["polygon"] == poly


def test_patch_polygon_does_not_touch_other_fields(incident_id):
    r = requests.post(f"{API}/incidents/{incident_id}/abschnitte",
                      json={"name": "TEST_EA_Mix", "farbe": "cyan",
                            "beschreibung": "preserve me", "aktiv": True})
    aid = r.json()["id"]
    poly = [[1.0, 2.0], [1.1, 2.1], [1.2, 2.2]]
    r2 = requests.patch(f"{API}/abschnitte/{aid}", json={"polygon": poly})
    assert r2.status_code == 200
    d = r2.json()
    assert d["name"] == "TEST_EA_Mix"
    assert d["farbe"] == "cyan"
    assert d["beschreibung"] == "preserve me"
    assert d["aktiv"] is True
    assert d["polygon"] == poly
