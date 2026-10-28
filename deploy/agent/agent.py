"""Linux-only, local deployment supervisor. No shell or client-selected commands.

Install outside the checkout, root-owned. Only root can approve release manifests.
The API UID can call four RPCs; mutations additionally require an offline secret.
"""

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import struct
import subprocess
import threading
import time
import uuid
from urllib.request import urlopen

ROOT = Path("/opt/els-mhd")
IMAGE = re.compile(r"ghcr\.io/davidstaffe/els-mhd-(api|web)@sha256:[0-9a-f]{64}")
BUSY = {"queued", "verify", "backup", "deploy", "health", "recover"}


class Refused(Exception):
    pass


def atomic(path, data, mode=0o600):
    """Durable replace including directory entry (power-loss boundary)."""
    path = Path(path)
    tmp = path.with_name("." + path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as stream:
        os.chmod(tmp, mode)
        json.dump(data, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    if os.name == "nt":  # Offline unit tests; production entry point is Linux-only.
        return
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read(path):
    return json.loads(Path(path).read_text())


def release_id(release):
    return hashlib.sha256(json.dumps(release, sort_keys=True).encode()).hexdigest()


class Engine:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.state_dir = self.root / "update-state"
        self.state_dir.mkdir(mode=0o700, exist_ok=True)
        self.mutex = threading.Lock()
        self.state_path = self.state_dir / "transaction.json"
        self.state = (
            read(self.state_path) if self.state_path.exists() else {"state": "idle"}
        )

    def run(self, args, *, stdin=None, timeout=180):
        try:
            result = subprocess.run(
                args,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=True,
                env={
                    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                    "HOME": "/nonexistent",
                    "DOCKER_CONFIG": str(self.root / "config/docker-client"),
                    "XDG_CACHE_HOME": "/tmp/els-mhd-cache",
                },
            )
            return result.stdout
        except (subprocess.SubprocessError, OSError):
            # Never forward Docker/DB output, paths, secrets or patient records.
            raise Refused(
                "Host-Schritt fehlgeschlagen; SSH-Prüfung erforderlich."
            ) from None

    def save(self, phase, **values):
        self.state = {**self.state, **values, "state": phase, "updated_at": time.time()}
        atomic(self.state_path, self.state)
        with open(self.state_dir / "audit.jsonl", "a", encoding="utf-8") as log:
            log.write(
                json.dumps(
                    {
                        "at": time.time(),
                        "state": phase,
                        "operation": self.state.get("id"),
                        "action": self.state.get("action"),
                        "version": self.state.get("target_version"),
                    }
                )
                + "\n"
            )
            log.flush()
            os.fsync(log.fileno())

    def approved(self, required=True):
        try:
            release = read(self.root / "config/approved-release.json")
        except FileNotFoundError:
            if required:
                raise Refused(
                    "Aktuell ist kein Release zur Installation freigegeben."
                ) from None
            return None
        if set(release) != {"version", "api", "web", "schema", "notes"}:
            raise Refused("Ungültige Releasefreigabe.")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", release["version"]):
            raise Refused("Ungültige Version.")
        if (
            release["schema"] != (2 if (self.root / "config/identity-required").exists() else 1)
            or not isinstance(release["notes"], str)
            or len(release["notes"]) > 4000
        ):
            raise Refused("Schemaänderungen benötigen eine manuelle Migration.")
        for service in ("api", "web"):
            match = IMAGE.fullmatch(release[service])
            if not match or match[1] != service:
                raise Refused("Nur freigegebene Registry-Digests erlaubt.")
        return release

    def active(self):
        return read(self.state_dir / "active.json")

    def identity_floor(self, release):
        if (self.root / "config/identity-required").exists() and release.get("schema") != 2:
            raise Refused("Version ohne persönliche Zugriffskontrolle gesperrt; geprüften Identity-Checkpoint verwenden.")

    def gate(self, enabled):
        atomic(
            self.root / "update-public/status.json",
            {"maintenance": enabled},
            mode=0o644,
        )

    def status(self, check=False):
        try:
            release = self.approved(required=False)
        except Refused:
            if check:
                raise
            release = None  # Invalid update approval must not hide rollback status.
        active = self.active()
        busy = self.state["state"] in BUSY or self.state["state"] == "recovery_required"
        return {
            "configured": True,
            "state": self.state["state"],
            "operation_id": self.state.get("id"),
            "message": (
                "Aktuell ist kein Release zur Installation freigegeben."
                if check and release is None
                else self.state.get("message", "")
            ),
            "last_error": self.state.get("error"),
            "running_version": active["version"],
            "available_version": release["version"] if release else None,
            "release_id": release_id(release) if release else None,
            "rollback_id": (
                release_id(read(self.state_dir / "previous.json"))
                if (self.state_dir / "previous.json").exists()
                else None
            ),
            "rollback_version": (
                read(self.state_dir / "previous.json")["version"]
                if (self.state_dir / "previous.json").exists()
                else None
            ),
            "notes": release["notes"] if release else "",
            "update_available": release != active if release else False,
            "can_install": not busy and release is not None and release != active,
            "can_rollback": not busy and (self.state_dir / "previous.json").exists() and (
                not (self.root / "config/identity-required").exists() or (
                    read(self.state_dir / "previous.json").get("schema") == 2
                    and read(self.state_dir / "previous.json") != active
                )
            ),
        }

    def authenticate(self, password):
        limits = self.state_dir / "attempts.json"
        now = time.time()
        entry = read(limits) if limits.exists() else {"until": 0, "count": 0}
        if now >= entry["until"]:
            entry = {"until": now + 300, "count": 0}
        if entry["count"] >= 5:
            raise Refused("Zu viele Freigabeversuche; fünf Minuten warten.")
        entry["count"] += 1
        atomic(limits, entry)
        encoded = (self.root / "config/update-password-hash").read_text().strip()
        algorithm, salt, expected = encoded.split("$")
        valid = False
        if (
            algorithm == "scrypt"
            and isinstance(password, str)
            and len(password) <= 1024
        ):
            actual = hashlib.scrypt(
                password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
            )
            valid = hmac.compare_digest(actual.hex(), expected)
        if not valid:
            with open(self.state_dir / "audit.jsonl", "a") as log:
                log.write(
                    json.dumps({"at": now, "action": "authorization_denied"}) + "\n"
                )
            raise Refused("Updatepasswort ungültig.")

    def compose(self, *args):
        # A root-owned, frozen Compose bundle includes admin and agent overlays.
        # active.json is the sole durable image authority for CLI and web actions.
        active = self.active()
        override = self.state_dir / "images.json"
        atomic(
            override,
            {"services": {name: {"image": active[name]} for name in ("api", "web")}},
        )
        return self.run(
            [
                "docker",
                "compose",
                "--project-name",
                "els-mhd",
                "--project-directory",
                str(self.root / "runtime"),
                "--env-file",
                str(self.root / "config/docker.env"),
                "-f",
                str(self.root / "runtime/compose.yaml"),
                "-f",
                str(override),
                *args,
            ],
            timeout=300,
        )

    def db(self, javascript):
        return self.run(
            [
                "docker",
                "exec",
                "els-mhd-db-1",
                "sh",
                "-c",
                'exec mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" '
                '--password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin '
                '--eval "$1"',
                "sh",
                javascript,
            ]
        )

    def safe(self):
        # Only a boolean crosses this boundary, never incident contents.
        out = self.db(
            'print(db.getSiblingDB("els_mhd").incidents.countDocuments('
            '{status:{$nin:["geplant","abgeschlossen","archiviert"]}}) === 0)'
        )
        if out.strip() != b"true":
            raise Refused("Aktive Einsätze: Vorgang gesperrt.")

    def health(self):
        identity_enabled = (self.root / "config/identity-required").exists()
        context = None
        base = "http://127.0.0.1:8080"
        if identity_enabled:
            import ssl
            from urllib.parse import urlparse
            base = (self.root / "config/identity-origin").read_text().strip()
            parsed = urlparse(base)
            if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.username:
                raise Refused("Ungültige geschützte HTTPS-Konfiguration.")
            context = ssl.create_default_context(cafile=str(self.root / "config/tls/ca.crt"))
        for _ in range(30):
            try:
                with urlopen(base + "/api/meta", timeout=3, context=context) as response:
                    if (
                        response.status == 200
                        and json.load(response).get("app") == "ELS MHD"
                    ):
                        with urlopen(base + "/", timeout=3, context=context) as web:
                            if web.status == 200:
                                self.db(
                                    'if (!db.getSiblingDB("els_mhd").runCommand({ping:1}).ok) quit(1)'
                                )
                                return
            except Exception:
                pass
            time.sleep(2)
        raise Refused("Gesundheitsprüfung fehlgeschlagen.")

    def backup(self):
        self.run(["/usr/local/lib/els-mhd/backup-mongodb.sh"], timeout=600)
        files = sorted(
            (self.root / "backups").glob("els-mhd-*.archive.gz"),
            key=lambda p: p.stat().st_mtime,
        )
        if not files or files[-1].stat().st_mtime < self.state["started_at"]:
            raise Refused("Kein frisches Backup.")
        archive = files[-1]
        # mongorestore parses the entire archive without writing the live database.
        with archive.open("rb") as stream:
            self.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    "els-mhd-db-1",
                    "sh",
                    "-c",
                    'exec mongorestore --username "$MONGO_INITDB_ROOT_USERNAME" '
                    '--password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin '
                    "--archive --gzip --dryRun --verbose",
                ],
                stdin=stream,
                timeout=600,
            )
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        # A real restore into an isolated namespace catches errors that a dry run
        # cannot. Application writers are stopped; compare collection counts.
        verify_db = "els_mhd_verify_" + uuid.uuid4().hex
        try:
            with archive.open("rb") as stream:
                self.run(
                    [
                        "docker",
                        "exec",
                        "-i",
                        "els-mhd-db-1",
                        "sh",
                        "-c",
                        'exec mongorestore --username "$MONGO_INITDB_ROOT_USERNAME" '
                        '--password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin '
                        '--archive --gzip --stopOnError --nsInclude="els_mhd.*" '
                        '--nsFrom="els_mhd.*" --nsTo="' + verify_db + '.*"',
                    ],
                    stdin=stream,
                    timeout=600,
                )
            result = self.db(
                'const a=db.getSiblingDB("els_mhd"),b=db.getSiblingDB("'
                + verify_db
                + '");'
                "print(a.getCollectionNames().every(n=>a.getCollection(n).countDocuments({})"
                "===b.getCollection(n).countDocuments({})))"
            )
            if result.strip() != b"true":
                raise Refused("Backup-Wiederherstellung konnte nicht bestätigt werden.")
        finally:
            self.db('db.getSiblingDB("' + verify_db + '").dropDatabase()')
        manifest = {"file": str(archive), "sha256": digest}
        atomic(self.state_dir / ("backup-" + self.state["id"] + ".json"), manifest)
        atomic(archive.with_suffix(".json"), manifest)
        self.run(["/usr/local/lib/els-mhd/backup-external.sh"], timeout=1800)

    def install(self):
        self.identity_floor(self.active())
        self.compose(
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--pull",
            "never",
            "--force-recreate",
            "api",
            "web",
        )

    def recover(self):
        """Called before accepting RPCs after any interrupted transaction."""
        if self.state["state"] not in BUSY:
            return
        try:
            if self.state["state"] in {"queued", "verify"}:
                self.save(
                    "failed",
                    message="Vorgang vor Änderungen abgebrochen. Bisherige Version bleibt aktiv.",
                )
                self.gate(False)
                return
            self.save(
                "recover",
                message="Unterbrochener Vorgang: vorherige Images wiederherstellen.",
            )
            # Persisted BEFORE stopping ingress or modifying active.json.
            atomic(self.state_dir / "active.json", self.state["before"])
            previous = self.state.get("before_previous")
            if previous:
                atomic(self.state_dir / "previous.json", previous)
            else:
                (self.state_dir / "previous.json").unlink(missing_ok=True)
            self.install()
            self.health()
            self.save(
                "failed",
                message="Vorherige Version wiederhergestellt; Datenbank unverändert.",
            )
            self.gate(False)
        except Exception:
            self.save(
                "recovery_required",
                message="Wiederherstellung fehlgeschlagen. SSH-Eingriff erforderlich.",
            )

    def execute(self, target):
        try:
            self.identity_floor(target)
            self.save("verify", message="Release und laufendes System prüfen.")
            expected = read(self.state_dir / "bundle.json")
            if (
                hashlib.sha256(
                    (self.root / "runtime/compose.yaml").read_bytes()
                ).hexdigest()
                != expected["sha256"]
            ):
                raise Refused(
                    "Compose-Konfiguration geändert. Manuelle Prüfung erforderlich."
                )
            self.health()
            self.safe()
            for name in ("api", "web"):
                container = self.compose("ps", "-q", name).decode().strip()
                actual = self.run(
                    ["docker", "inspect", "--format", "{{.Image}}", container]
                ).strip()
                pinned = self.run(
                    [
                        "docker",
                        "image",
                        "inspect",
                        "--format",
                        "{{.Id}}",
                        self.active()[name],
                    ]
                ).strip()
                if actual != pinned:
                    raise Refused("Laufende Images weichen vom Checkpoint ab.")
            for service in ("api", "web"):
                if self.state.get("action") == "apply":
                    self.run(["docker", "pull", target[service]], timeout=900)
                else:
                    # A rollback must work offline, including the initial local
                    # SHA256 image checkpoint captured during provisioning.
                    self.run(["docker", "image", "inspect", target[service]])
            self.gate(True)
            self.save(
                "backup",
                message="Wartungsfenster: Schreibzugriffe stoppen und Backup prüfen.",
            )
            # Stop ingress and ALL application writers, then recheck after draining.
            # DB remains running. No window for a concurrent incident creation.
            self.compose("stop", "-t", "60", "web", "api")
            self.safe()
            self.backup()
            self.save("deploy", message="Freigegebene Images starten.")
            atomic(self.state_dir / "active.json", target)
            self.install()
            self.save("health", message="WebApp und Datenbankverbindung prüfen.")
            self.health()
            atomic(self.state_dir / "previous.json", self.state["before"])
            self.save("complete", message="Vorgang erfolgreich abgeschlossen.")
            self.gate(False)
        except Exception as exc:
            # Always bounded recovery, including failure before first container change.
            self.save(
                self.state["state"],
                error=(
                    str(exc) if isinstance(exc, Refused) else "Vorgang fehlgeschlagen."
                ),
            )
            self.recover()
        finally:
            self.mutex.release()

    def dispatch(self, request):
        action = request.get("action")
        if action not in {"status", "check", "apply", "rollback"}:
            raise Refused("Unzulässige Aktion.")
        if action in {"status", "check"}:
            return self.status(check=action == "check")
        if set(request) != {"action", "password", "version", "release_id"}:
            raise Refused("Ungültige Freigabe.")
        if not self.mutex.acquire(blocking=False):
            raise Refused("Ein Vorgang läuft bereits.")
        try:
            self.authenticate(request["password"])
            if self.state["state"] in BUSY | {"recovery_required"}:
                raise Refused("Wiederherstellung erforderlich.")
            target = (
                self.approved()
                if action == "apply"
                else read(self.state_dir / "previous.json")
            )
            self.identity_floor(target)
            if (
                request["version"] != target["version"]
                or request["release_id"] != release_id(target)
                or target == self.active()
            ):
                raise Refused(
                    "Release wurde geändert oder ist bereits aktiv. Erneut prüfen."
                )
            self.state = {
                "id": uuid.uuid4().hex,
                "action": action,
                "before": self.active(),
                "before_previous": (
                    read(self.state_dir / "previous.json")
                    if (self.state_dir / "previous.json").exists()
                    else None
                ),
                "target_version": target["version"],
                "started_at": time.time(),
            }
            self.save(
                "queued", message="Vorgang angenommen; kurzes Wartungsfenster folgt."
            )
            accepted = self.status()
            thread = threading.Thread(target=self.execute, args=(target,), daemon=False)
            thread.start()
            return accepted
        except Exception:
            self.mutex.release()
            raise


def main():
    import fcntl

    os.umask(0o077)
    # Shared with legacy deployment/checkpoint entry points.
    lock = open(ROOT / "rollback/.deploy.lock", "a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    engine = Engine()
    engine.recover()
    if engine.state["state"] in {"complete", "failed", "idle"}:
        engine.health()
        engine.gate(False)
    address = "/run/els-mhd-update/agent.sock"
    if os.path.exists(address):
        os.unlink(address)

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(10)
            _, uid, _ = struct.unpack(
                "3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            )
            if uid not in (0, 10001):
                return
            try:
                line = self.rfile.readline(8193)
                if len(line) > 8192:
                    raise Refused("Anfrage zu groß.")
                result = {"ok": True, "data": engine.dispatch(json.loads(line))}
            except Refused as exc:
                result = {"ok": False, "error": str(exc)}
            except Exception:
                result = {
                    "ok": False,
                    "error": "Host-Dienst nicht bereit. Konfiguration über SSH prüfen.",
                }
            self.wfile.write(json.dumps(result).encode() + b"\n")

    with socketserver.ThreadingUnixStreamServer(address, Handler) as server:
        os.chown(address, 0, 10001)
        os.chmod(address, 0o660)
        server.serve_forever()


if __name__ == "__main__":
    main()
