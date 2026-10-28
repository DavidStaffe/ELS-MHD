"""Interactive offline provisioning. Prints neither password nor encryption key.

Run only after reviewing deployment instructions. Existing secrets are preserved.
"""

import getpass
import hashlib
import os
from pathlib import Path
import secrets
import sys
from cryptography.fernet import Fernet


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: python provision_admin.py <Secret-Verzeichnis>")
    target = Path(sys.argv[1])
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    password_file = target / "admin_password_hash"
    key_file = target / "config_encryption_key"
    if password_file.exists():
        raise SystemExit(
            "Administratorpasswort existiert bereits; keine Änderung vorgenommen."
        )
    password = getpass.getpass("Neues Administratorpasswort (mindestens 14 Zeichen): ")
    if not 14 <= len(password) <= 1024 or password != getpass.getpass(
        "Passwort wiederholen: "
    ):
        raise SystemExit("Passwörter stimmen nicht überein oder sind zu kurz.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    encoded = f"scrypt${salt.hex()}${digest.hex()}"
    for path, value in (
        (password_file, encoded),
        (key_file, Fernet.generate_key().decode()),
    ):
        if path == key_file and path.exists():
            continue  # Never rotate the encryption key implicitly.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
    print(
        "Administratorzugang eingerichtet. Secret-Dateien separat sichern und Container-Leserechte prüfen."
    )


if __name__ == "__main__":
    main()
