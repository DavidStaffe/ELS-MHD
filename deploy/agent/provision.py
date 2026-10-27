"""Offline, root-only initialization after reviewing the frozen Compose bundle.

Does not deploy containers. Captures actually running image IDs, never :latest.
"""

import getpass
import hashlib
import os
import secrets
import sys
from agent import Engine, ROOT, atomic


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit("sudo python3 provision.py <current-version>")
    engine = Engine()
    if (engine.state_dir / "active.json").exists():
        raise SystemExit("Already provisioned; refusing to overwrite checkpoint.")
    if not __import__("re").fullmatch(r"[A-Za-z0-9._-]{1,80}", sys.argv[1]):
        raise SystemExit("Invalid version.")
    (ROOT / "update-public").mkdir(mode=0o755, exist_ok=True)
    password = getpass.getpass("Separates Updatepasswort (mindestens 14 Zeichen): ")
    if not 14 <= len(password) <= 1024 or password != getpass.getpass("Wiederholen: "):
        raise SystemExit("Passwörter ungültig.")
    salt = secrets.token_bytes(16)
    hashed = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
    secret = ROOT / "config/update-password-hash"
    with os.fdopen(
        os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
    ) as stream:
        stream.write(f"scrypt${salt.hex()}${hashed}")
    active = {
        "version": sys.argv[1],
        "schema": 1,
        "notes": "Initial verified checkpoint",
    }
    for name in ("api", "web"):
        active[name] = (
            engine.run(
                ["docker", "inspect", "--format", "{{.Image}}", f"els-mhd-{name}-1"]
            )
            .decode()
            .strip()
        )
        engine.run(["docker", "image", "inspect", active[name]])
    atomic(
        engine.state_dir / "bundle.json",
        {
            "sha256": hashlib.sha256(
                (ROOT / "runtime/compose.yaml").read_bytes()
            ).hexdigest()
        },
    )
    atomic(engine.state_dir / "active.json", active)
    engine.gate(False)
    print("Checkpoint und Updatepasswort gespeichert. Noch kein Update gestartet.")


if __name__ == "__main__":
    main()
