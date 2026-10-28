"""Explicit operator-only provisioning. Never called automatically at startup.

python identity_setup.py --new-install (empty installation only)
python identity_setup.py --adopt-existing (deliberate legacy migration)
"""

import argparse
import asyncio
import json
import os
import secrets
import uuid
from pathlib import Path
from core.identity import db, digest, indexes


def marker_path():
    return Path(
        os.environ.get("ELS_IDENTITY_STATE_FILE", "/var/lib/els/identity-state.json")
    )


async def provision(adopt_existing=False):
    path = marker_path()
    if (
        path.exists()
        or await db.identity_state.find_one({"_id": "setup"})
        or await db.users.count_documents({})
    ):
        raise RuntimeError(
            "Identitätseinrichtung existiert. Kein erneutes Bootstrap erlaubt."
        )
    collections = await db.list_collection_names()
    populated = any(
        [
            await db[c].count_documents({})
            for c in collections
            if c not in {"auth_limits"}
        ]
    )
    if populated and not adopt_existing:
        raise RuntimeError(
            "Vorhandene Installation: ausdrücklich --adopt-existing verwenden."
        )
    await indexes()
    code, setup_id = secrets.token_urlsafe(32), str(uuid.uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create BEFORE database state: interruption leaves a closed setup.
    with path.open("x", encoding="utf-8") as f:
        os.chmod(path, 0o600)
        json.dump({"setup_id": setup_id, "state": "pending"}, f)
        f.flush()
        os.fsync(f.fileno())
    await db.identity_state.insert_one(
        {
            "_id": "setup",
            "setup_id": setup_id,
            "state": "pending",
            "setup_hash": digest(code),
        }
    )
    print("Einmaliger Setup-Code (sicher verwahren, nicht protokollieren): " + code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--new-install", action="store_true")
    group.add_argument("--adopt-existing", action="store_true")
    args = parser.parse_args()
    asyncio.run(provision(args.adopt_existing))
