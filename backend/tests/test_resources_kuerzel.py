"""Backend tests for ResourceBase.kuerzel feature (iteration 23).

Covers:
- POST /api/incidents/{id}/resources with kuerzel persists
- GET resources returns stored kuerzel
- PATCH /api/resources/{id} with kuerzel updates value
- Pydantic max_length=4 validation -> 422
- Backward-compat: POST without kuerzel -> kuerzel is null
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def incident(session):
    name = f"TEST_KUERZEL_{uuid.uuid4().hex[:6]}"
    r = session.post(f"{API}/incidents", json={"name": name, "typ": "veranstaltung"})
    assert r.status_code in (200, 201), r.text
    inc = r.json()
    yield inc
    try:
        session.delete(f"{API}/incidents/{inc['id']}")
    except Exception:
        pass


# --- POST kuerzel persists --------------------------------------------------

def test_create_resource_with_kuerzel_persists(session, incident):
    payload = {
        "name": "Rettungswagen 01",
        "kuerzel": "RTW1",
        "typ": "intern",
        "kategorie": "rtw",
    }
    r = session.post(f"{API}/incidents/{incident['id']}/resources", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Rettungswagen 01"
    assert body["kuerzel"] == "RTW1"
    assert "id" in body
    rid = body["id"]

    # GET list -> verify persistence
    g = session.get(f"{API}/incidents/{incident['id']}/resources")
    assert g.status_code == 200
    matches = [x for x in g.json() if x["id"] == rid]
    assert len(matches) == 1
    assert matches[0]["kuerzel"] == "RTW1"


# --- POST without kuerzel -> null ------------------------------------------

def test_create_resource_without_kuerzel_is_null(session, incident):
    payload = {"name": "RTW kein Kuerzel", "typ": "intern", "kategorie": "rtw"}
    r = session.post(f"{API}/incidents/{incident['id']}/resources", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kuerzel"] is None


# --- PATCH kuerzel update --------------------------------------------------

def test_patch_resource_updates_kuerzel(session, incident):
    create = session.post(
        f"{API}/incidents/{incident['id']}/resources",
        json={"name": "Patch Target", "kuerzel": "OLD", "typ": "intern", "kategorie": "rtw"},
    )
    assert create.status_code == 201
    rid = create.json()["id"]

    p = session.patch(f"{API}/resources/{rid}", json={"kuerzel": "RTW9"})
    assert p.status_code == 200, p.text
    assert p.json()["kuerzel"] == "RTW9"

    # GET back to verify persistence
    g = session.get(f"{API}/incidents/{incident['id']}/resources")
    assert g.status_code == 200
    matches = [x for x in g.json() if x["id"] == rid]
    assert matches[0]["kuerzel"] == "RTW9"


# --- PATCH max_length validation -------------------------------------------

def test_patch_resource_kuerzel_too_long_returns_422(session, incident):
    create = session.post(
        f"{API}/incidents/{incident['id']}/resources",
        json={"name": "Validate Target", "typ": "intern", "kategorie": "rtw"},
    )
    rid = create.json()["id"]

    bad = session.patch(f"{API}/resources/{rid}", json={"kuerzel": "TOOLONG"})
    assert bad.status_code == 422, bad.text
    body = bad.json()
    # FastAPI returns {"detail": [...]} with validation errors
    flat = str(body).lower()
    assert "at most 4" in flat or "max_length" in flat or "string_too_long" in flat


# --- POST max_length validation --------------------------------------------

def test_post_resource_kuerzel_too_long_returns_422(session, incident):
    bad = session.post(
        f"{API}/incidents/{incident['id']}/resources",
        json={"name": "X", "kuerzel": "ABCDE", "typ": "intern", "kategorie": "rtw"},
    )
    assert bad.status_code == 422, bad.text


# --- Edge: exactly 4 chars passes ------------------------------------------

def test_create_resource_kuerzel_exactly_4_chars_ok(session, incident):
    r = session.post(
        f"{API}/incidents/{incident['id']}/resources",
        json={"name": "Edge4", "kuerzel": "ABCD", "typ": "intern", "kategorie": "rtw"},
    )
    assert r.status_code == 201
    assert r.json()["kuerzel"] == "ABCD"
