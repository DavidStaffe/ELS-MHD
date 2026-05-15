"""Backend tests for Phase 1 OSM map feature.

Covers:
- POST /api/incidents with ort_lat/ort_lng/ort_zoom (valid + validation)
- PATCH /api/incidents/{id} partial location update
- PATCH /api/resources/{id} with lat/lng/divera_id/fms_status (valid + validation)
- POST /api/incidents/{id}/resources accepts new location/fms fields
"""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"
TIMEOUT = 30


@pytest.fixture(scope="module")
def incident_id():
    r = requests.post(
        f"{API}/incidents",
        json={
            "name": "TEST_MAP_INC",
            "typ": "veranstaltung",
            "ort": "Hamburg",
            "ort_lat": 53.5511,
            "ort_lng": 9.9937,
            "ort_zoom": 15,
        },
        timeout=30,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    yield data["id"]
    # cleanup
    requests.delete(f"{API}/incidents/{data['id']}", timeout=30)


# --- Incidents location fields ---------------------------------------------


def test_incident_create_with_location_persists():
    r = requests.post(
        f"{API}/incidents",
        json={
            "name": "TEST_LOC_PERSIST",
            "typ": "veranstaltung",
            "ort": "Berlin",
            "ort_lat": 52.52,
            "ort_lng": 13.405,
            "ort_zoom": 14,
        },
        timeout=30,
    )
    assert r.status_code == 201, r.text
    inc = r.json()
    assert inc["ort_lat"] == 52.52
    assert inc["ort_lng"] == 13.405
    assert inc["ort_zoom"] == 14
    # GET verify
    g = requests.get(f"{API}/incidents/{inc['id']}", timeout=30)
    assert g.status_code == 200
    gj = g.json()
    assert gj["ort_lat"] == 52.52
    assert gj["ort_lng"] == 13.405
    assert gj["ort_zoom"] == 14
    requests.delete(f"{API}/incidents/{inc['id']}", timeout=30)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ort_lat", 95.0),
        ("ort_lat", -95.0),
        ("ort_lng", 200.0),
        ("ort_lng", -181.0),
        ("ort_zoom", 0),
        ("ort_zoom", 23),
    ],
)
def test_incident_create_rejects_invalid_geo(field, value):
    body = {
        "name": "TEST_BAD",
        "typ": "veranstaltung",
        "ort": "x",
        "ort_lat": 53.5,
        "ort_lng": 10.0,
        "ort_zoom": 15,
    }
    body[field] = value
    r = requests.post(f"{API}/incidents", json=body, timeout=30)
    assert r.status_code == 422, f"{field}={value} should 422 but got {r.status_code}: {r.text}"


def test_incident_patch_partial_location(incident_id):
    r = requests.patch(
        f"{API}/incidents/{incident_id}",
        json={"ort_lat": 48.137, "ort_lng": 11.575},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ort_lat"] == 48.137
    assert data["ort_lng"] == 11.575
    # zoom not changed
    assert data["ort_zoom"] == 15


def test_incident_patch_invalid_lat_returns_422(incident_id):
    r = requests.patch(
        f"{API}/incidents/{incident_id}",
        json={"ort_lat": 91.0},
        timeout=30,
    )
    assert r.status_code == 422, r.text


# --- Resources location & FMS ----------------------------------------------


@pytest.fixture(scope="module")
def resource_id(incident_id):
    r = requests.post(
        f"{API}/incidents/{incident_id}/resources",
        json={
            "name": "TEST_RTW_MAP",
            "typ": "intern",
            "kategorie": "rtw",
            "lat": 53.55,
            "lng": 9.99,
            "divera_id": "DIV-123",
            "fms_status": 2,
        },
        timeout=30,
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    yield rid
    requests.delete(f"{API}/resources/{rid}", timeout=30)


def test_resource_create_accepts_location_and_fms(incident_id, resource_id):
    """POST /incidents/{id}/resources must persist lat/lng/divera_id/fms_status."""
    lst = requests.get(f"{API}/incidents/{incident_id}/resources", timeout=30).json()
    res = next(x for x in lst if x["id"] == resource_id)
    assert res.get("lat") == 53.55, f"lat not persisted on create: {res}"
    assert res.get("lng") == 9.99
    assert res.get("divera_id") == "DIV-123"
    assert res.get("fms_status") == 2


def test_resource_patch_set_location(resource_id, incident_id):
    r = requests.patch(
        f"{API}/resources/{resource_id}",
        json={"lat": 53.6, "lng": 10.0, "fms_status": 3},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["lat"] == 53.6
    assert data["lng"] == 10.0
    assert data["fms_status"] == 3


@pytest.mark.parametrize("fms", [-1, 10, 99])
def test_resource_patch_rejects_invalid_fms(resource_id, fms):
    r = requests.patch(
        f"{API}/resources/{resource_id}",
        json={"fms_status": fms},
        timeout=30,
    )
    assert r.status_code == 422, f"fms={fms} should 422 got {r.status_code}"


def test_resource_patch_rejects_invalid_lat(resource_id):
    r = requests.patch(
        f"{API}/resources/{resource_id}",
        json={"lat": 200.0},
        timeout=30,
    )
    assert r.status_code == 422


def test_resource_divera_id_max_length(incident_id):
    r = requests.post(
        f"{API}/incidents/{incident_id}/resources",
        json={
            "name": "TEST_DIVERA_LONG",
            "typ": "intern",
            "kategorie": "rtw",
            "divera_id": "x" * 65,
        },
        timeout=30,
    )
    assert r.status_code == 422


def test_resource_unplace_clears_lat_lng(resource_id, incident_id):
    """Setting lat/lng to null must clear them so resource becomes 'unplaced'."""
    # First ensure resource has lat/lng
    requests.patch(f"{API}/resources/{resource_id}", json={"lat": 53.5, "lng": 9.9}, timeout=30)
    # Try to unplace
    r = requests.patch(
        f"{API}/resources/{resource_id}",
        json={"lat": None, "lng": None},
        timeout=30,
    )
    # Should succeed (200) AND clear lat/lng
    assert r.status_code in (200, 400), r.text
    if r.status_code == 200:
        data = r.json()
        assert data.get("lat") is None, f"lat should be cleared but is {data.get('lat')}"
        assert data.get("lng") is None
    else:
        # If 400 (no changes) - bug: cannot unset via PATCH with exclude_none
        pytest.fail(
            "PATCH cannot clear lat/lng because exclude_none=True drops nulls. "
            "Unplace flow will be broken."
        )
