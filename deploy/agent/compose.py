"""SSH fallback: same durable image authority and deployment lock as the agent.

Read-only status/config permitted. Start/recreate only via agent; this helper is
for starting the pinned application after a reboot with the agent stopped.
"""

import os
import sys
import fcntl
from agent import Engine, ROOT, BUSY

if os.geteuid() != 0 or sys.argv[1:] not in (["status"], ["start"]):
    raise SystemExit("sudo python3 compose.py status|start")
with open(ROOT / "rollback/.deploy.lock", "a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    engine = Engine()
    if engine.state["state"] in BUSY | {"recovery_required"}:
        raise SystemExit("Resolve interrupted transaction using agent recovery first.")
    if sys.argv[1] == "status":
        print(engine.compose("ps").decode())
    else:
        engine.install()
        engine.health()
        engine.gate(False)
