#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
cd /opt/els-mhd/app
exec 9>/opt/els-mhd/rollback/.deploy.lock
flock -n 9 || { echo "Another deployment is running" >&2; exit 1; }
state=/opt/els-mhd/rollback/current.env
[[ -f "$state" ]] || { echo "Missing rollback checkpoint" >&2; exit 1; }
# The checkpoint was generated locally by create-rollback-checkpoint.sh.
source "$state"
[[ "$API_IMAGE" =~ ^els-mhd-api:rollback-[0-9]{8}-[0-9]{6}$ ]] || exit 1
[[ "$WEB_IMAGE" =~ ^els-mhd-web:rollback-[0-9]{8}-[0-9]{6}$ ]] || exit 1
[[ -z $(git status --porcelain) ]] || { echo "Dirty working tree" >&2; exit 1; }
docker image inspect "$API_IMAGE" "$WEB_IMAGE" >/dev/null
saved_compose="/opt/els-mhd/rollback/compose-${CHECKPOINT}.yaml"
[[ -f "$saved_compose" ]] || { echo "Saved Compose configuration missing" >&2; exit 1; }
rollback_compose=(docker compose --project-directory /opt/els-mhd/app/deploy --env-file /opt/els-mhd/config/docker.env -f "$saved_compose")
"${rollback_compose[@]}" config --quiet
compose=(docker compose --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml)
deployed=0
rollback() {
 code=$?
 trap - ERR
 echo "Update failed; restoring old application image tags" >&2
 docker tag "$API_IMAGE" els-mhd-api:latest
 docker tag "$WEB_IMAGE" els-mhd-web:latest
 if [[ "$deployed" -eq 1 ]]; then
   echo "Recreating application containers using rollback images" >&2
   "${rollback_compose[@]}" up -d --no-deps --no-build --force-recreate api web || true
 fi
 exit "$code"
}
# Install the failure handler BEFORE any Docker build changes the latest tags.
trap rollback ERR
echo "Backing up MongoDB locally..."
systemctl start els-mhd-backup.service
[[ "$(systemctl show -p Result --value els-mhd-backup.service)" = success ]] || false
echo "Ensuring the chained encrypted external backup has completed successfully..."
# If the OnSuccess job is still running, systemctl waits for its start job.
systemctl start els-mhd-external-backup.service
[[ "$(systemctl show -p Result --value els-mhd-external-backup.service)" = success ]] || false
echo "Building new application images..."
"${compose[@]}" build api web
echo "Starting updated application containers; leaving MongoDB untouched..."
deployed=1
"${compose[@]}" up -d --no-deps --no-build --force-recreate api web
echo "Checking application endpoints..."
ok=0
for i in {1..30}; do
 if curl -fsS --max-time 4 http://127.0.0.1:8080/ >/dev/null &&
    curl -fsS --max-time 4 http://127.0.0.1:8080/api/meta >/dev/null; then
   ok=1
   break
 fi
 sleep 2
done
[[ "$ok" -eq 1 ]] || { echo "HTTP checks failed" >&2; false; }
trap - ERR
echo "Update passed HTTP checks; rollback checkpoint remains intact."
