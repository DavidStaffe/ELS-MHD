"""One-time, interactive Pi bootstrap. No sudoers change or root shell.

Run ONLY a reviewed, root-installed copy with its reviewed root-owned source
snapshot. The user supplies sudo and, if needed, a NEW admin password locally.
No password is embedded in source. All runtime state lives outside the checkout.
"""

import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from agent import Engine, ROOT, atomic

SOURCE = Path("/opt/els-mhd/bootstrap-source")
PENDING = Path("/opt/els-mhd/config/pending-update-password-hash")


def check_source():
    """Never build root-executed images from a mutable user's checkout."""
    for parent in (SOURCE, *SOURCE.parents):
        info = parent.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError(
                "Source parents must be root-owned and not group/world writable."
            )
    for path in SOURCE.rglob("*"):
        info = path.lstat()
        if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError(
                "Source must be a root-owned snapshot without symlinks or writable files."
            )


def secret(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)


def share_api_secret(path):
    """Compose bind-mounted secrets retain host UID/GID/mode.

    Only the API's supplementary group may read these two files. Their parent
    stays root-only; the separate host update password stays root:root 0600.
    """
    if path.is_symlink() or path.stat().st_uid != 0:
        raise RuntimeError("API secret must be a root-owned regular file.")
    os.chown(path, 0, 10001)
    os.chmod(path, 0o440)


def password_hash(password):
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
    return f"scrypt${salt.hex()}${value}"


def smoke(engine, target, db_image):
    """Independent stack, independent volume, only synthetic credentials/data."""
    project = "els-mhd-smoke-" + uuid.uuid4().hex[:12]
    directory = ROOT / project
    directory.mkdir(mode=0o700)
    fixture_password = secrets.token_urlsafe(32)
    secret(directory / "admin", password_hash(fixture_password))
    secret(
        directory / "cipher", base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    )
    share_api_secret(directory / "admin")
    share_api_secret(directory / "cipher")
    mongo_password = secrets.token_hex(32)
    config = {
        "services": {
            "db": {
                "image": db_image,
                "environment": {
                    "MONGO_INITDB_ROOT_USERNAME": "synthetic",
                    "MONGO_INITDB_ROOT_PASSWORD": mongo_password,
                },
                "volumes": ["synthetic-data:/data/db"],
            },
            "api": {
                "image": target["api"],
                "environment": {
                    "MONGO_URL": f"mongodb://synthetic:{mongo_password}@db:27017/?authSource=admin",
                    "DB_NAME": "synthetic_only",
                    "ELS_ADMIN_PASSWORD_HASH_FILE": "/run/secrets/admin",
                    "ELS_CONFIG_ENCRYPTION_KEY_FILE": "/run/secrets/cipher",
                },
                "secrets": ["admin", "cipher"],
                "group_add": ["10001"],
                "depends_on": ["db"],
            },
            "web": {
                "image": target["web"],
                "ports": ["127.0.0.1::80"],
                "depends_on": ["api"],
            },
        },
        "volumes": {"synthetic-data": {}},
        "secrets": {
            "admin": {"file": str(directory / "admin")},
            "cipher": {"file": str(directory / "cipher")},
        },
    }
    compose = directory / "compose.json"
    atomic(compose, config)
    command = ["docker", "compose", "-p", project, "-f", str(compose)]
    try:
        engine.run([*command, "up", "-d", "--no-build", "--pull", "never"], timeout=300)
        port = engine.run([*command, "port", "web", "80"]).decode().strip()
        if not re.fullmatch(r"127\.0\.0\.1:\d+", port):
            raise RuntimeError("Unexpected test stack endpoint.")
        base = "http://" + port
        for _ in range(90):
            try:
                with urlopen(base + "/api/meta", timeout=3) as response:
                    if json.load(response).get("app") == "ELS MHD":
                        break
            except Exception:
                pass
            time.sleep(2)
        else:
            raise RuntimeError("Synthetic stack health failed.")
        with urlopen(base + "/api/system/updates/status", timeout=10) as response:
            if json.load(response).get("configured") is not False:
                raise RuntimeError("Synthetic stack must not access the live agent.")

        def post(path, payload, expected, token=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            request = Request(
                base + path, data=json.dumps(payload).encode(), headers=headers
            )
            try:
                with urlopen(request, timeout=15) as response:
                    status, data = response.status, json.load(response)
            except HTTPError as error:
                status, data = error.code, {}
            if status != expected:
                raise RuntimeError(
                    f"Synthetic authentication check failed: {path} "
                    f"(HTTP {status}, expected {expected})."
                )
            return data

        approval = {
            "password": "synthetic",
            "version": "synthetic",
            "release_id": "0" * 64,
        }
        post("/api/system/updates/apply", approval, 401)
        post("/api/system/updates/rollback", approval, 401)
        post("/api/admin/login", {"password": "incorrect-synthetic"}, 401)
        session = post("/api/admin/login", {"password": fixture_password}, 200)
        post("/api/system/updates/apply", approval, 503, session["token"])
    finally:
        # Only this explicitly named, random synthetic project is ever removed.
        engine.run([*command, "down", "--volumes"], timeout=180)
        shutil.rmtree(directory)


def main():
    import fcntl

    if os.geteuid() != 0 or len(sys.argv) != 1:
        raise SystemExit("Run this reviewed installer with sudo, without arguments.")
    os.umask(0o077)
    check_source()
    if (SOURCE / "backend/core/identity.py").exists():
        raise RuntimeError("Persönliche Identität benötigt migrate_identity.py; der Legacy-Shared-Passwort-Bootstrap ist gesperrt.")
    for name in ("update-state", "rollback", "runtime", "backups", "config"):
        (ROOT / name).mkdir(mode=0o700, exist_ok=True)
    public = ROOT / "update-public"
    public.mkdir(mode=0o755, exist_ok=True)
    os.chmod(public, 0o755)
    with open(ROOT / "rollback/.deploy.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        engine = Engine()
        if (engine.state_dir / "active.json").exists():
            raise RuntimeError(
                "Already provisioned; this one-time installer will not overwrite state."
            )
        engine.safe()
        engine.health()
        engine.run(["mountpoint", "-q", "/mnt/els-mhd-backup"])
        if shutil.disk_usage(ROOT).free < 8 * 1024**3:
            raise RuntimeError("At least 8 GiB free space required.")
        # Capture running IDs, not mutable tags. No application data is printed.
        current = {
            "version": "pre-web-updates",
            "schema": 1,
            "notes": "Initial running image checkpoint",
        }
        for name in ("api", "web"):
            current[name] = (
                engine.run(
                    ["docker", "inspect", "--format", "{{.Image}}", f"els-mhd-{name}-1"]
                )
                .decode()
                .strip()
            )
        database = json.loads(engine.run(["docker", "inspect", "els-mhd-db-1"]))[0]
        api = json.loads(engine.run(["docker", "inspect", "els-mhd-api-1"]))[0]
        revision = (SOURCE / "BOOTSTRAP_REVISION").read_text().strip()
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise RuntimeError("Invalid reviewed source revision.")
        target = {
            "version": "commit-" + revision[:12],
            "schema": 1,
            "notes": "Reviewed ARM64 bootstrap",
        }
        for name, folder in (("api", "backend"), ("web", "frontend")):
            tag = f"els-mhd-{name}:release-{revision[:12]}"
            print("Build:", name, flush=True)
            engine.run(
                ["docker", "build", "--tag", tag, str(SOURCE / folder)], timeout=3600
            )
            target[name] = (
                engine.run(["docker", "image", "inspect", "--format", "{{.Id}}", tag])
                .decode()
                .strip()
            )
        print("Prüfe isolierten ARM64-Teststack …", flush=True)
        smoke(engine, target, database["Config"]["Image"])
        secrets_dir = ROOT / "config/secrets"
        admin = secrets_dir / "admin_password_hash"
        cipher = secrets_dir / "config_encryption_key"
        if not admin.exists():
            first = getpass.getpass(
                "Neues Administratorpasswort (mindestens 14 Zeichen): "
            )
            if not 14 <= len(first) <= 1024 or first != getpass.getpass(
                "Administratorpasswort wiederholen: "
            ):
                raise RuntimeError("Administratorpasswörter ungültig.")
            secret(admin, password_hash(first))
        if not cipher.exists():
            secret(cipher, base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        share_api_secret(admin)
        share_api_secret(cipher)
        encoded = PENDING.read_text().strip()
        if not re.fullmatch(r"scrypt\$[0-9a-f]{32}\$[0-9a-f]{128}", encoded):
            raise RuntimeError("Invalid pending update password hash.")
        installed_secret = ROOT / "config/update-password-hash"
        if installed_secret.exists():
            raise RuntimeError(
                "Existing update password preserved; use the dedicated rotation procedure."
            )
        secret(installed_secret, encoded)
        PENDING.unlink()
        command = [
            "docker",
            "compose",
            "-p",
            "els-mhd",
            "--env-file",
            str(ROOT / "config/docker.env"),
            "-f",
            str(SOURCE / "deploy/compose.yaml"),
            "-f",
            str(SOURCE / "deploy/compose.updates.yaml"),
            "config",
            "--format",
            "json",
        ]
        config = json.loads(engine.run(command))
        db_config = config["services"]["db"]
        actual_env = dict(
            item.split("=", 1) for item in database["Config"]["Env"] if "=" in item
        )
        if db_config["image"] != database["Config"]["Image"] or any(
            db_config["environment"].get(k) != actual_env.get(k)
            for k in ("MONGO_INITDB_ROOT_USERNAME", "MONGO_INITDB_ROOT_PASSWORD")
        ):
            raise RuntimeError(
                "Database config differs; migration requires separate review."
            )
        live_mounts = {
            item.get("Name")
            for item in database["Mounts"]
            if item["Destination"] == "/data/db"
        }
        expected_mounts = {
            config["volumes"][v["source"]]["name"]
            for v in db_config.get("volumes", [])
            if v["target"] == "/data/db"
        }
        if live_mounts != expected_mounts:
            raise RuntimeError("Database volume differs; refusing bootstrap.")
        for name in ("api", "web"):
            config["services"][name].pop("build", None)
        env = config["services"]["api"].setdefault("environment", {})
        env.update(
            {
                "ELS_ADMIN_PASSWORD_HASH_FILE": "/run/secrets/admin_password_hash",
                "ELS_CONFIG_ENCRYPTION_KEY_FILE": "/run/secrets/config_encryption_key",
            }
        )
        legacy = next(
            (
                item.split("=", 1)[1]
                for item in api["Config"]["Env"]
                if item.startswith("DIVERA_API_KEY=")
            ),
            "",
        )
        if legacy:
            env["DIVERA_API_KEY"] = legacy
        config["services"]["api"]["secrets"] = [
            {"source": name, "target": name}
            for name in ("admin_password_hash", "config_encryption_key")
        ]
        config["secrets"] = {
            name: {"file": str(secrets_dir / name)}
            for name in ("admin_password_hash", "config_encryption_key")
        }
        atomic(ROOT / "runtime/compose.yaml", config)
        atomic(
            engine.state_dir / "bundle.json",
            {
                "sha256": hashlib.sha256(
                    (ROOT / "runtime/compose.yaml").read_bytes()
                ).hexdigest()
            },
        )
        destination = Path("/usr/local/lib/els-mhd")
        destination.mkdir(mode=0o755, parents=True, exist_ok=True)
        for path in (SOURCE / "deploy/agent").glob("*.py"):
            shutil.copyfile(path, destination / path.name)
            os.chmod(destination / path.name, 0o644)
        for name in ("backup-mongodb.sh", "backup-external.sh"):
            contents = (SOURCE / "scripts" / name).read_text()
            if name == "backup-external.sh":
                disk_uuid = (
                    engine.run(
                        [
                            "findmnt",
                            "-n",
                            "-o",
                            "UUID",
                            "--mountpoint",
                            "/mnt/els-mhd-backup",
                        ]
                    )
                    .decode()
                    .strip()
                )
                if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", disk_uuid):
                    raise RuntimeError("Unexpected USB UUID.")
                contents = re.sub(
                    r"^UUID=.*$", "UUID=" + disk_uuid, contents, flags=re.M
                )
            path = destination / name
            path.write_text(contents)
            os.chmod(path, 0o700)
        shutil.copyfile(
            SOURCE / "deploy/systemd/els-mhd-update-agent.service",
            "/etc/systemd/system/els-mhd-update-agent.service",
        )
        atomic(engine.state_dir / "active.json", current)
        engine.gate(False)
        engine.state = {
            "id": uuid.uuid4().hex,
            "action": "bootstrap",
            "before": current,
            "before_previous": None,
            "target_version": target["version"],
            "started_at": time.time(),
        }
        engine.save("queued", message="Geprüfter Erstaufbau der Web-Updateverwaltung.")
        engine.mutex.acquire()
        engine.execute(target)
        if engine.state["state"] != "complete":
            raise RuntimeError(
                "Bootstrap failed: " + engine.state.get("error", engine.state["state"])
            )
    engine.run(["systemctl", "daemon-reload"])
    engine.run(["systemctl", "enable", "--now", "els-mhd-update-agent.service"])
    print(
        "Installation abgeschlossen. Updatepasswort gesetzt; Host-Agent aktiv.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Installation abgebrochen:", str(error), file=sys.stderr)
        raise SystemExit(1)
