#!/bin/sh
# Run only from a reviewed, root-owned source snapshot. No application deploy.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run reviewed installer as root'; exit 1; }
[ "$#" = 1 ] && [ "$1" = '--apply' ] || { echo 'Usage: install.sh --apply (see docs/certificate-onboarding.md)'; exit 1; }
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec 9>/opt/els-mhd/rollback/.deploy.lock
flock -n 9 || { echo 'Deployment busy'; exit 1; }
export SOURCE
/usr/bin/python3 - <<'PY'
import hashlib, json, os, pathlib, sys
root = pathlib.Path('/opt/els-mhd')
source = pathlib.Path(os.environ['SOURCE'])
for path in [source, *source.parents, *source.rglob('*')]:
    stat = path.lstat()
    if path.is_symlink() or stat.st_uid != 0 or stat.st_mode & 0o022:
        raise SystemExit('Require root-owned source and parents, without writable files/symlinks')
if (root / 'config/identity-required').read_text().strip() != '2':
    raise SystemExit('Require schema 2')
transaction = root / 'update-state/transaction.json'
state = json.loads(transaction.read_text()) if transaction.exists() else {'state': 'idle'}
if state['state'] not in ('idle', 'complete', 'failed'):
    raise SystemExit('Resolve update/recovery first')
if json.loads((root / 'update-state/active.json').read_text())['schema'] != 2:
    raise SystemExit('Require schema-2 active release')
expected = json.loads((root / 'update-state/bundle.json').read_text())['sha256']
if hashlib.sha256((root / 'runtime/compose.yaml').read_bytes()).hexdigest() != expected:
    raise SystemExit('Runtime bundle differs; review first')
sys.path.insert(0, str(source / 'deploy/onboarding'))
from server import assets
print('Public CA SHA-256:', assets((root / 'config/tls/ca.crt').read_bytes())['/fingerprint.txt'][1].decode())
PY
ip -4 -o addr show dev wlan0 | grep -Eq ' inet 10\.0\.0\.1/24 ' || { echo 'Expected hotspot 10.0.0.1/24 on wlan0'; exit 1; }
openssl verify -check_ss_sig -CAfile /opt/els-mhd/config/tls/ca.crt /opt/els-mhd/config/tls/ca.crt
systemd-analyze verify "$SOURCE/deploy/systemd/els-mhd-onboarding.service" "$SOURCE/deploy/systemd/els-mhd-onboarding.socket"
install -d -m 755 /usr/local/lib/els-mhd-onboarding
install -m 644 "$SOURCE/deploy/onboarding/server.py" "$SOURCE/deploy/onboarding/index.html" /usr/local/lib/els-mhd-onboarding/
install -m 644 "$SOURCE/deploy/systemd/els-mhd-onboarding.service" "$SOURCE/deploy/systemd/els-mhd-onboarding.socket" /etc/systemd/system/
systemctl daemon-reload
systemctl stop els-mhd-onboarding.service els-mhd-onboarding.socket
systemctl enable --now els-mhd-onboarding.socket
echo 'Onboarding enabled. Perform hotspot and non-hotspot acceptance checks from the documentation.'
