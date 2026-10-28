"""Reviewed root-only upgrade of an EXISTING frozen ELS-MHD installation.

Default: preflight only. --apply explicitly installs; never invoked by CI or API.
Existing database configuration, volume and credentials remain authoritative.
Any failure after stopping ingress leaves maintenance on; no insecure rollback.
"""

import argparse
import base64
import copy
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import time

from agent import Engine, ROOT, BUSY, atomic, read
from bootstrap import SOURCE, check_source, secret, share_api_secret


def hostname(value):
    try:
        ipaddress.ip_address(value)
    except ValueError:
        if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?", value):
            raise ValueError("Gültiger LAN-Hostname oder gültige IP erforderlich.")
    return value


def bundle(previous, root, host, images):
    result = copy.deepcopy(previous)
    api, web = result["services"]["api"], result["services"]["web"]
    for name, service in (("api", api), ("web", web)):
        service.pop("build", None)
        service["image"] = images[name]
    env = api.setdefault("environment", {})
    if (
        not isinstance(env, dict)
        or not env.get("MONGO_URL")
        or env.get("DB_NAME") != "els_mhd"
    ):
        raise ValueError("Vorhandene DB-Konfiguration muss eindeutig sein.")
    env.update(
        CORS_ORIGINS="https://" + host,
        ELS_IDENTITY_STATE_FILE="/var/lib/els/identity-state.json",
        ELS_MAINTENANCE_FILE="/run/els-mhd-maintenance/status.json",
    )
    # Preserve both DIVERA encryption-key generations and every existing mount.
    env.pop("ELS_ADMIN_PASSWORD", None)
    groups = api.setdefault("group_add", [])
    if "10001" not in map(str, groups):
        groups.append("10001")
    volumes = api.setdefault("volumes", [])
    if any(not isinstance(v, dict) for v in volumes):
        raise ValueError(
            "Nur die gerenderte, geprüfte Compose-Konfiguration verwenden."
        )
    if not any(v.get("target") == "/var/lib/els" for v in volumes):
        result.setdefault("volumes", {})["identity_state"] = {
            "name": "els-mhd_identity_state"
        }
        volumes.append(
            {"type": "volume", "source": "identity_state", "target": "/var/lib/els"}
        )
    for v in volumes:
        if v.get("target") == "/var/lib/els" and (
            v.get("type") != "volume" or v.get("read_only")
        ):
            raise ValueError(
                "Identitätszustand braucht ein schreibbares persistentes Volume."
            )
    if not any(v.get("target") == "/run/els-mhd-maintenance" for v in volumes):
        volumes.append(
            {
                "type": "bind",
                "source": str(root / "update-public"),
                "target": "/run/els-mhd-maintenance",
                "read_only": True,
            }
        )
    if not env.get("ELS_CONFIG_ENCRYPTION_KEY_FILE") and not env.get(
        "ELS_CONFIG_ENCRYPTION_KEY"
    ):
        env["ELS_CONFIG_ENCRYPTION_KEY_FILE"] = "/run/secrets/identity_config_key"
        result.setdefault("secrets", {})["identity_config_key"] = {
            "file": str(root / "config/secrets/identity_config_key")
        }
        api.setdefault("secrets", []).append(
            {"source": "identity_config_key", "target": "identity_config_key"}
        )
    web_volumes = web.setdefault("volumes", [])
    web["volumes"] = [
        v
        for v in web_volumes
        if v.get("target")
        not in {
            "/etc/nginx/conf.d/default.conf",
            "/run/tls",
            "/run/tls/server.crt",
            "/run/tls/server.key",
        }
    ] + [
        {
            "type": "bind",
            "source": str(root / "runtime/nginx-identity.conf"),
            "target": "/etc/nginx/conf.d/default.conf",
            "read_only": True,
        },
        {
            "type": "bind",
            "source": str(root / "config/tls/server.crt"),
            "target": "/run/tls/server.crt",
            "read_only": True,
        },
        {
            "type": "bind",
            "source": str(root / "config/tls/server.key"),
            "target": "/run/tls/server.key",
            "read_only": True,
        },
    ]
    ports = web.setdefault("ports", [])
    if not any(str(p.get("target")) == "443" for p in ports):
        ports.append(
            {"target": 443, "published": "443", "protocol": "tcp", "host_ip": "0.0.0.0"}
        )
    if result["services"]["db"] != previous["services"]["db"]:
        raise ValueError("DB-Konfiguration darf nicht geändert werden.")
    return result


def tls(engine, root, host):
    directory = root / "config/tls"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    names = [directory / n for n in ("ca.key", "ca.crt", "server.key", "server.crt")]
    if not any(p.exists() for p in names):
        san = ("IP:" if _is_ip(host) else "DNS:") + host
        ext = directory / "server.ext"
        secret(
            ext,
            "subjectAltName="
            + san
            + ",DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n",
        )
        engine.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:3072",
                "-nodes",
                "-days",
                "3650",
                "-subj",
                "/CN=ELS-MHD local CA",
                "-keyout",
                str(names[0]),
                "-out",
                str(names[1]),
            ]
        )
        engine.run(
            [
                "openssl",
                "req",
                "-newkey",
                "rsa:3072",
                "-nodes",
                "-subj",
                "/CN=" + host,
                "-keyout",
                str(names[2]),
                "-out",
                str(directory / "server.csr"),
            ]
        )
        engine.run(
            [
                "openssl",
                "x509",
                "-req",
                "-days",
                "397",
                "-in",
                str(directory / "server.csr"),
                "-CA",
                str(names[1]),
                "-CAkey",
                str(names[0]),
                "-CAcreateserial",
                "-extfile",
                str(ext),
                "-out",
                str(names[3]),
            ]
        )
    if not all(
        p.is_file() and not p.is_symlink() and p.stat().st_uid == 0 for p in names
    ):
        raise RuntimeError("TLS-Konfiguration unvollständig oder nicht rootgeschützt.")
    engine.run(["openssl", "verify", "-CAfile", str(names[1]), str(names[3])])
    engine.run(
        ["openssl", "x509", "-in", str(names[3]), "-noout", "-checkend", "2592000"]
    )
    engine.run(
        [
            "openssl",
            "x509",
            "-in",
            str(names[3]),
            "-noout",
            "-checkip" if _is_ip(host) else "-checkhost",
            host,
        ]
    )


def _is_ip(value):
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", type=hostname, default="10.0.0.1")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit(
            "Lokal mit sudo ausführen. Ohne --apply wird nichts installiert."
        )
    os.umask(0o077)
    check_source()
    for directory in (ROOT / "config", ROOT / "runtime", ROOT / "update-state"):
        for path in (directory, *directory.rglob("*")):
            info = path.lstat()
            if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
                raise RuntimeError(
                    "Host-Konfiguration muss rootgeschützt und ohne Symlinks sein."
                )
    engine = Engine()
    previous = read(ROOT / "runtime/compose.yaml")
    active = engine.active()
    if active.get("schema") != 1 or (ROOT / "config/identity-required").exists():
        raise RuntimeError(
            "Erstmigration nur einmal aus Schema 1. Vorhandenen Zustand nicht überschreiben."
        )
    if engine.state["state"] in BUSY | {"recovery_required"}:
        raise RuntimeError("Laufenden/unterbrochenen Updatevorgang zuerst klären.")
    engine.safe()
    if shutil.disk_usage(ROOT).free < 8 * 1024**3:
        raise RuntimeError("Mindestens 8 GiB freier Speicher erforderlich.")
    if _is_ip(args.hostname):
        addresses = json.loads(engine.run(["ip", "-j", "address"]))
        if args.hostname not in {
            a.get("local")
            for interface in addresses
            for a in interface.get("addr_info", [])
        }:
            raise RuntimeError("Ziel-IP ist auf diesem Pi nicht eingerichtet.")
    if (
        engine.db(
            'print(db.getSiblingDB("els_mhd").users.countDocuments({}) === 0)'
        ).strip()
        != b"true"
    ):
        raise RuntimeError(
            "Vorhandene persönliche Konten benötigen eine gesonderte Migration."
        )
    database = json.loads(engine.run(["docker", "inspect", "els-mhd-db-1"]))[0]
    actual = {
        m.get("Name") for m in database["Mounts"] if m["Destination"] == "/data/db"
    }
    expected = {
        previous["volumes"][m["source"]]["name"]
        for m in previous["services"]["db"]["volumes"]
        if m["target"] == "/data/db"
    }
    if actual != expected or not actual or None in actual:
        raise RuntimeError("DB-Volume weicht von der eingefrorenen Installation ab.")
    engine.run(["mountpoint", "-q", "/mnt/els-mhd-backup"])
    revision = (SOURCE / "BOOTSTRAP_REVISION").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("Geprüfte Commit-ID fehlt.")
    bundle(previous, ROOT, args.hostname, {"api": active["api"], "web": active["web"]})
    if not args.apply:
        print(
            "Vorprüfung bestanden. Keine Installation durchgeführt. Ziel: https://"
            + args.hostname
        )
        return
    if (engine.state_dir / "identity-migration.json").exists():
        raise RuntimeError(
            "Migrationsjournal existiert. Unterbrechung lokal prüfen; nicht erneut starten."
        )
    if (
        input(
            "Wartungsfenster, Backup und Zieladresse geprüft? INSTALLIEREN eingeben: "
        )
        != "INSTALLIEREN"
    ):
        raise RuntimeError("Abgebrochen.")
    tls(engine, ROOT, args.hostname)
    images = {}
    for name, folder in (("api", "backend"), ("web", "frontend")):
        tag = f"els-mhd-{name}:identity-{revision[:12]}"
        print("Baue geprüftes Image:", name, flush=True)
        engine.run(["docker", "build", "-t", tag, str(SOURCE / folder)], timeout=3600)
        images[name] = (
            engine.run(["docker", "image", "inspect", "--format", "{{.Id}}", tag])
            .decode()
            .strip()
        )
    updated = bundle(previous, ROOT, args.hostname, images)
    # No database/container changes before the deployment mutex and drained writers.
    engine.run(["systemctl", "stop", "els-mhd-update-agent.service"])
    import fcntl

    with open(ROOT / "rollback/.deploy.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fresh = Engine()
        if (
            fresh.state["state"] in BUSY | {"recovery_required"}
            or fresh.active() != active
            or read(ROOT / "runtime/compose.yaml") != previous
        ):
            raise RuntimeError(
                "Update/Konfiguration während des Builds geändert. Vor Migration lokal prüfen und Host-Dienst wieder starten."
            )
        engine.safe()
        journal = engine.state_dir / "identity-migration.json"
        atomic(journal, {"phase": "maintenance", "revision": revision})
        engine.gate(True)
        engine.compose("stop", "-t", "60", "web", "api")
        engine.safe()
        engine.state.update(id=secrets.token_hex(16), started_at=time.time())
        engine.backup()
        archive = ROOT / "backups" / ("identity-config-" + revision[:12])
        archive.mkdir(mode=0o700)
        shutil.copy2(ROOT / "runtime/compose.yaml", archive / "compose.json")
        atomic(archive / "active.json", active)
        key = ROOT / "config/secrets/identity_config_key"
        if not key.exists():
            secret(key, base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
            share_api_secret(key)
        shutil.copyfile(
            SOURCE / "frontend/deploy/nginx-https.conf",
            ROOT / "runtime/nginx-identity.conf",
        )
        secret(ROOT / "config/identity-origin", "https://" + args.hostname)
        secret(ROOT / "config/identity-required", "2\n")
        target = {
            "version": "identity-" + revision[:12],
            "schema": 2,
            "notes": "Geprüfter Identitäts-Checkpoint",
            **images,
        }
        atomic(ROOT / "runtime/compose.yaml", updated)
        atomic(
            engine.state_dir / "bundle.json",
            {
                "sha256": hashlib.sha256(
                    (ROOT / "runtime/compose.yaml").read_bytes()
                ).hexdigest()
            },
        )
        atomic(engine.state_dir / "active.json", target)
        # Safe offline rollback starts at the SAME identity-capable checkpoint.
        atomic(engine.state_dir / "previous.json", target)
        shutil.copytree(ROOT / "config", archive / "config")
        atomic(archive / "identity-compose.json", updated)
        engine.run(["/usr/local/lib/els-mhd/backup-external.sh"], timeout=1800)
        atomic(journal, {"phase": "install", "revision": revision})
        engine.install()
        engine.health()
        code = (
            engine.compose(
                "exec", "-T", "api", "python", "identity_setup.py", "--adopt-existing"
            )
            .decode()
            .strip()
        )
        for path in (SOURCE / "deploy/agent").glob("*.py"):
            shutil.copyfile(path, Path("/usr/local/lib/els-mhd") / path.name)
        atomic(journal, {"phase": "complete", "revision": revision})
        engine.gate(False)
    engine.run(["systemctl", "daemon-reload"])
    print(code)
    engine.run(["systemctl", "start", "els-mhd-update-agent.service"])
    print(
        "HTTPS bereit: https://"
        + args.hostname
        + " – lokale CA auf Arbeitsplätzen vertrauen, dann Setup abschließen."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never log runtime config, credentials, setup code or subprocess output.
        raise SystemExit(
            "Migration abgebrochen. Nach Beginn bleibt Wartung aktiv; Migrationsjournal und geschützte Host-Logs lokal prüfen. Kein automatischer Rückfall auf ungeschützte Images."
        )
