"""Offline disaster recovery only. NEVER called through the web RPC.

Stop the agent first. Restoring discards writes since the selected backup.
"""

import fcntl
import hashlib
import os
from pathlib import Path
import re
import sys
from agent import Engine, ROOT, read


def main():
    if (
        os.geteuid() != 0
        or len(sys.argv) != 2
        or not re.fullmatch(r"[a-f0-9]{32}", sys.argv[1])
    ):
        raise SystemExit("sudo python3 restore.py <operation-id>")
    with open(ROOT / "rollback/.deploy.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        engine = Engine()
        manifest = read(engine.state_dir / ("backup-" + sys.argv[1] + ".json"))
        archive = Path(manifest["file"]).resolve(strict=True)
        if archive.parent != ROOT / "backups" or not re.fullmatch(
            r"els-mhd-\d{8}-\d{6}\.archive\.gz", archive.name
        ):
            raise SystemExit("Invalid backup path.")
        with archive.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["sha256"]:
                raise SystemExit("Backup checksum mismatch. No changes made.")
        if input("Restore discards newer data. Type RESTORE to confirm: ") != "RESTORE":
            raise SystemExit("Cancelled.")
        engine.safe()
        engine.gate(True)
        engine.compose("stop", "-t", "60", "web", "api")
        engine.safe()
        # Parser verification before any destructive restore.
        base = ["docker", "exec", "-i", "els-mhd-db-1", "sh", "-c"]
        command = (
            'exec mongorestore --username "$MONGO_INITDB_ROOT_USERNAME" '
            '--password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin '
            '--archive --gzip --nsInclude="els_mhd.*" '
        )
        with archive.open("rb") as stream:
            engine.run(
                [*base, command + "--dryRun --verbose"], stdin=stream, timeout=600
            )
        # Existing DB is not dropped wholesale. Supported schema is unchanged;
        # archive collections replace their counterparts, no other databases touched.
        with archive.open("rb") as stream:
            engine.run(
                [*base, command + "--drop --stopOnError"], stdin=stream, timeout=600
            )
        print(
            "Restore completed. Maintenance remains enabled. Verify data and pinned images over SSH before reopening."
        )


if __name__ == "__main__":
    main()
