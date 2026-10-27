"""Bounded repair for a stale API bind mount after agent RuntimeDirectory removal.

No arguments, no password rotation, no builds, no database/volume changes.
Refuses active incidents and incomplete transactions. Recreates only the API
from its existing pinned image, then tests a real supervisor restart.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path('/opt/els-mhd')
STAGE = Path('/home/els-mhd/.cache/els-mhd-deploy')
LIBRARY = Path('/usr/local/lib/els-mhd')
UNIT = Path('/etc/systemd/system/els-mhd-update-agent.service')
DIRECTORY = Path('/run/els-mhd-update')
OLD_AGENT = '9e4dd9d04c5444720afdd6ac008353839b0ff4fe6fbdb7502248de8b3ad83435'
NEW_AGENT = '6dff75eaa271202b82cb8b9459ab3cea3182d8bcd3ff360ee5daa4f24d55a9a8'
OLD_UNIT = '10211d766de730958aa888f608fe14c8aeb00bb79fb93557df06a33c651d56ec'
NEW_UNIT = '733fb2b450584ad62e4dda9070ecc70c2140681f3800825cac4d8bba5c6b4bca'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def replace(path, contents, mode=0o644):
    temporary = path.with_name('.' + path.name + '.socket-repair')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def service(*args):
    subprocess.run(['systemctl', *args], timeout=120, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def verify():
    for _ in range(30):
        try:
            with urlopen('http://127.0.0.1:8080/api/system/updates/check', timeout=5) as response:
                value = json.load(response)
            if (value.get('configured') and value.get('state') == 'complete'
                    and value.get('can_rollback') and value.get('update_available') is False
                    and value.get('can_install') is False):
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError('API cannot reach the supervisor through its mounted socket directory.')


def main():
    import fcntl
    if os.geteuid() != 0 or len(sys.argv) != 1:
        raise SystemExit('Run this bounded repair with sudo, without arguments.')
    os.umask(0o077)
    candidate = STAGE / 'agent-release-status.py'
    candidate_unit = STAGE / 'els-mhd-update-agent-preserve.service'
    installed = LIBRARY / 'agent.py'
    if digest(candidate) != NEW_AGENT or digest(candidate_unit) != NEW_UNIT:
        raise SystemExit('Repair checksum mismatch; no changes made.')
    if digest(installed) not in (OLD_AGENT, NEW_AGENT) or digest(UNIT) not in (OLD_UNIT, NEW_UNIT):
        raise SystemExit('Unexpected installed revision; no changes made.')
    if installed.is_symlink() or UNIT.is_symlink() or DIRECTORY.is_symlink():
        raise SystemExit('Unexpected symbolic link; no changes made.')
    state = json.loads((ROOT / 'update-state/transaction.json').read_text())
    if state['state'] != 'complete':
        raise SystemExit('A deployment needs attention; no changes made.')
    protected = [ROOT / 'update-state' / name for name in ('active.json', 'previous.json')]
    protected.append(ROOT / 'config/update-password-hash')
    original = {path: digest(path) for path in protected}
    sys.path.insert(0, str(LIBRARY))
    from agent import Engine
    engine = Engine()
    engine.health()
    engine.safe()
    before_agent = installed.read_bytes()
    lock = None
    stopped = False
    repair_started = False
    try:
        engine.gate(True)
        engine.safe()
        if json.loads(engine.state_path.read_text())['state'] != 'complete':
            raise RuntimeError('A deployment has started meanwhile.')
        service('stop', 'els-mhd-update-agent.service')
        stopped = True
        repair_started = True
        lock = open(ROOT / 'rollback/.deploy.lock', 'a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        replace(UNIT, candidate_unit.read_bytes())
        replace(installed, candidate.read_bytes())
        service('daemon-reload')
        # The old systemd unit may have removed this directory on stop. It must
        # exist BEFORE Compose binds it; future service stops preserve its inode.
        DIRECTORY.mkdir(mode=0o755, exist_ok=True)
        os.chown(DIRECTORY, 0, 0)
        os.chmod(DIRECTORY, 0o755)
        print('Wartungsfenster: API mit unverändertem Image neu verbinden.', flush=True)
        engine.compose('stop', '-t', '60', 'api')
        engine.safe()
        engine.compose('up', '-d', '--no-deps', '--no-build', '--pull', 'never', '--force-recreate', 'api')
        engine.health()
        lock.close()
        lock = None
        service('start', 'els-mhd-update-agent.service')
        stopped = False
        verify()
        container = engine.run(['docker', 'inspect', '--format', '{{.Id}}', 'els-mhd-api-1'])
        inode = DIRECTORY.stat().st_ino
        print('Prüfe Host-Agent-Neustart ohne API-Containerwechsel.', flush=True)
        service('restart', 'els-mhd-update-agent.service')
        verify()
        if DIRECTORY.stat().st_ino != inode:
            raise RuntimeError('Socket directory was replaced during service restart.')
        if engine.run(['docker', 'inspect', '--format', '{{.Id}}', 'els-mhd-api-1']) != container:
            raise RuntimeError('Unexpected API container replacement.')
        if any(digest(path) != checksum for path, checksum in original.items()):
            raise RuntimeError('Pinned images, rollback or password changed unexpectedly.')
        print('Reparatur erfolgreich: Updateprüfung und Rollbackstatus erreichbar, Agent-Neustart geprüft. Passwort und Version unverändert.', flush=True)
    except Exception as error:
        if not repair_started:
            engine.gate(False)
            raise SystemExit('Reparatur vor Änderungen abgebrochen: ' + str(error))
        if lock:
            lock.close()
        # Keep the corrected directory lifetime, even when restoring old code.
        # Bring the same pinned API back; never restore older database contents.
        try:
            replace(installed, before_agent)
            engine.compose('up', '-d', '--no-deps', '--no-build', '--pull', 'never', 'api')
            engine.health()
            service('start', 'els-mhd-update-agent.service')
            engine.gate(False)
        except Exception:
            print('Wartung bleibt gesperrt; SSH-Prüfung erforderlich.', file=sys.stderr)
        raise SystemExit('Socket-Reparatur abgebrochen: ' + str(error))


if __name__ == '__main__':
    main()
