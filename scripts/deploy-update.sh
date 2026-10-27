#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
cd /opt/els-mhd/app
exec 9>/opt/els-mhd/rollback/.deploy.lock
flock -n 9 || exit 1
state=/opt/els-mhd/rollback/current.env
[[ -f "$state" ]] || { echo "Missing rollback checkpoint" >&2; exit 1; }
source "$state"
[[ "$API_IMAGE" =~ ^els-mhd-api:rollback-[0-9]{8}-[0-9]{6}$ ]] || exit 1
[[ "$WEB_IMAGE" =~ ^els-mhd-web:rollback-[0-9]{8}-[0-9]{6}$ ]] || exit 1
[[ -z $(git status --porcelain) ]] || { echo "Dirty working tree" >&2; exit 1; }
docker image inspect "$API_IMAGE" "$WEB_IMAGE" >/dev/null
echo "Backing up MongoDB locally..."
systemctl start els-mhd-backup.service
echo "Backing up MongoDB externally..."
systemctl start els-mhd-external-backup.service
echo "Building new images..."
docker compose --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml build api web
rollback() {
 code=$?
 trap - ERR
 echo "Update failed; restoring old images" >&2
 docker tag "$API_IMAGE" els-mhd-api:latest
 docker tag "$WEB_IMAGE" els-mhd-web:latest
 docker compose --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml up -d --no-build --force-recreate api web || true
 exit "$code"
}
trap rollback ERR
docker compose --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml up -d --no-build --force-recreate api web
ok=0
for i in {1..30}; do
 if curl -fsS --max-time 4 http://127.0.0.1:8080/ >/dev/null && curl -fsS --max-time 4 http://127.0.0.1:8080/api/meta >/dev/null; then ok=1; break; fi
 sleep 2
done
[[ "$ok" -eq 1 ]] || false
trap - ERR
echo "Update successful; rollback images preserved"
