"""Host-owned persistent maintenance barrier; unreadable state fails closed."""

import json
import os
from pathlib import Path


def in_maintenance():
    path = os.environ.get("ELS_MAINTENANCE_FILE")
    if not path:
        return False
    try:
        return json.loads(Path(path).read_text())["maintenance"] is not False
    except (OSError, ValueError, KeyError):
        return True
