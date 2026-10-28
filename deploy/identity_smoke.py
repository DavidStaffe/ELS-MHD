"""Real HTTPS/Mongo/Docker integration check; synthetic projects ONLY.

Never use this to initialize a live installation. No credentials are printed.
"""
import argparse
import json
import re
import secrets
import subprocess
import time
from urllib.parse import urlparse

import requests


def run(project, env_file, origin, ca):
    if not re.fullmatch(r"els-mhd-test-[a-z0-9-]+", project):
        raise RuntimeError("Only explicitly named synthetic projects are allowed.")
    if urlparse(origin).hostname not in {"localhost", "127.0.0.1"} or urlparse(origin).scheme != "https":
        raise RuntimeError("Synthetic checks require verified loopback HTTPS.")
    compose = ["docker", "compose", "-p", project, "--env-file", env_file,
               "-f", "deploy/compose.yaml", "-f", "deploy/compose.https.yaml"]

    def command(*args, success=True):
        result = subprocess.run([*compose, *args], capture_output=True, text=True, timeout=180)
        if success and result.returncode:
            raise RuntimeError("Synthetic container operation failed; inspect protected container logs.")
        return result

    container = command("ps", "-q", "db").stdout.strip()
    metadata = json.loads(subprocess.check_output(["docker", "inspect", container]))[0]
    if metadata["Config"]["Labels"].get("com.docker.compose.project") != project:
        raise RuntimeError("Unexpected database project.")
    volumes = [m for m in metadata["Mounts"] if m["Destination"] == "/data/db"]
    if len(volumes) != 1 or not volumes[0].get("Name", "").startswith(project + "_"):
        raise RuntimeError("Synthetic database must use its own disposable named volume.")
    anonymous = requests.Session()
    anonymous.verify = ca
    for _ in range(90):
        try:
            if anonymous.get(origin + "/api/meta", timeout=3).status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    else:
        raise RuntimeError("Synthetic HTTPS stack did not become healthy.")

    def api(client, method, path, payload=None, expected=200):
        response = client.request(method, origin + "/api" + path, json=payload, timeout=30)
        if response.status_code != expected:
            # Do not include bodies: setup/login responses contain one-time secrets.
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code}, expected {expected}")
        return response.json() if response.content else {}

    api(anonymous, "GET", "/incidents", expected=401)
    api(anonymous, "GET", "/system/updates/status", expected=401)
    setup_output = command("exec", "-T", "api", "python", "identity_setup.py", "--new-install").stdout
    code = setup_output.strip().split(": ")[-1]
    initial = api(anonymous, "POST", "/auth/setup", {"code": code, "username": "test-admin", "display_name": "Synthetic Administrator"})

    def login(username, password):
        client = requests.Session()
        client.verify = ca
        result = api(client, "POST", "/auth/login", {"username": username, "password": password})
        client.headers["X-CSRF-Token"] = result["csrf"]
        return client

    def change_password(client, password):
        result = api(client, "POST", "/auth/password", {"password": password})
        client.headers["X-CSRF-Token"] = result["csrf"]

    admin_password, el_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    admin = login("test-admin", initial["initial_password"])
    api(admin, "GET", "/auth/users", expected=428)
    change_password(admin, admin_password)
    api(admin, "GET", "/system/updates/status")
    account = api(admin, "POST", "/auth/users", {"username": "test-el", "display_name": "Synthetic EL", "eligible": ["EL"], "permissions": ["incidents.create", "archives.patients.correct"]}, expected=201)
    el = login("test-el", account["initial_password"])
    change_password(el, el_password)
    incident = api(el, "POST", "/incidents", {"name": "Synthetic integration check", "el_user_id": account["user"]["id"]}, expected=201)
    iid = incident["id"]
    patient = api(el, "POST", f"/incidents/{iid}/patients", {"sichtung": "S2", "notiz": "Synthetic only"}, expected=201)
    pid = patient["id"]
    api(admin, "GET", f"/patients/{pid}", expected=403)
    api(anonymous, "GET", f"/patients/{pid}", expected=401)
    resources = api(el, "GET", f"/incidents/{iid}/resources")
    resource = next(r for r in resources if r["kategorie"] == "evt")
    api(el, "POST", f"/patients/{pid}/assign-resource", {"resource_id": resource["id"]})
    second = api(el, "POST", f"/incidents/{iid}/patients", {"sichtung": "S3"}, expected=201)
    api(el, "POST", f"/patients/{second['id']}/assign-resource", {"resource_id": resource["id"]}, expected=409)
    api(el, "POST", "/auth/lock")
    api(el, "GET", f"/patients/{pid}", expected=423)
    api(el, "POST", "/auth/unlock", {"password": el_password})
    api(el, "POST", f"/incidents/{iid}/close", {"reason": "Synthetic closure"}, expected=409)
    api(el, "POST", f"/incidents/{iid}/close", {"reason": "Synthetic closure", "confirm_open": True})
    api(el, "POST", f"/incidents/{iid}/corrections/patients/{pid}", {"reason": "Synthetic correction", "changes": {"notiz": "Corrected synthetic note"}})
    assert api(el, "GET", f"/incidents/{iid}")["status"] == "abgeschlossen"
    after = api(el, "GET", f"/patients/{pid}")
    assert after["zugewiesene_ressource_id"] == resource["id"]
    assert after["versions"][-1]["before"]["notiz"] == "Synthetic only"
    api(el, "POST", f"/incidents/{iid}/reopen", {"reason": "Synthetic reopen"})
    command("restart", "api", "web")
    for _ in range(60):
        try:
            if anonymous.get(origin + "/api/meta", timeout=3).status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    el = login("test-el", el_password)
    assert api(el, "GET", f"/patients/{pid}")["notiz"] == "Corrected synthetic note"
    assert command("exec", "-T", "api", "python", "identity_setup.py", "--new-install", success=False).returncode != 0
    api(anonymous, "POST", "/auth/setup", {"code": code, "username": "again", "display_name": "Forbidden"}, expected=403)
    api(el, "POST", "/auth/logout")
    api(el, "GET", f"/patients/{pid}", expected=401)
    print("PASS: real MongoDB, verified TLS, bootstrap, accounts, CSRF sessions, RBAC, resource capacity, lock, archive correction, reopen, restart persistence, setup replay, logout")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--ca", required=True)
    args = parser.parse_args()
    run(args.project, args.env_file, args.origin, args.ca)
