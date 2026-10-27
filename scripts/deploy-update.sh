#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
cd /opt/els-mhd/app
exec 9>/opt/els-mhd/rollback/.deploy.lock
flock -n 9 || { echo "Another deployment is running" >&2; exit 1; }
state=/opt/els-mhd/rollback/current.env
[[ -f "$state" ]] || { echo "Missing rollback checkpoint" >&2; exit 1; }
source "$state"
[[ "$CHECKPOINT" =~ ^[0-9]{8}-[0-9]{6}$ ]] || exit 1
[[ "$API_IMAGE" == "els-mhd-api:rollback-$CHECKPOINT" ]] || exit 1
[[ "$WEB_IMAGE" == "els-mhd-web:rollback-$CHECKPOINT" ]] || exit 1
[[ -z $(git status --porcelain) ]] || { echo "Dirty working tree" >&2; exit 1; }
docker image inspect "$API_IMAGE" "$WEB_IMAGE" >/dev/null
saved_compose="/opt/els-mhd/rollback/compose-$CHECKPOINT.yaml"
[[ -f "$saved_compose" ]] || { echo "Saved Compose configuration missing" >&2; exit 1; }
# Until schema/network/volume migrations are supported, forbid Compose changes.
cmp -s deploy/compose.yaml "$saved_compose" || { echo "Compose changed; migration procedure required" >&2; exit 1; }
sha=$(git rev-parse --short=12 HEAD)
api_release="els-mhd-api:release-$sha"
web_release="els-mhd-web:release-$sha"
active_override=/opt/els-mhd/rollback/active-images.compose.yaml
[[ ! -e "$active_override" ]] || { echo "Existing active release override: establish new checkpoint before next deployment" >&2; exit 1; }
tmp=$(mktemp /opt/els-mhd/rollback/.release-XXXXXXXX.yaml)
trap 'rm -f "$tmp"' EXIT
printf 'services:\n  api:\n    image: %s\n  web:\n    image: %s\n' "$api_release" "$web_release" > "$tmp"
compose=(docker compose --project-directory /opt/els-mhd/app/deploy --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml -f "$tmp")
"${compose[@]}" config --quiet
rollback_tmp=$(mktemp /opt/els-mhd/rollback/.rollback-XXXXXXXX.yaml)
trap 'rm -f "$tmp" "$rollback_tmp"' EXIT
printf 'services:\n  api:\n    image: %s\n  web:\n    image: %s\n' "$API_IMAGE" "$WEB_IMAGE" > "$rollback_tmp"
rollback_compose=(docker compose --project-directory /opt/els-mhd/app/deploy --env-file /opt/els-mhd/config/docker.env -f "$saved_compose" -f "$rollback_tmp")
"${rollback_compose[@]}" config --quiet
deployed=0
rollback() {
  code=$?
  trap - ERR
  echo "Update failed; trying pinned rollback images" >&2
  if [[ "$deployed" -eq 1 ]]; then
    "${rollback_compose[@]}" up -d --no-deps --no-build --force-recreate api web || true
  fi
  rm -f "$active_override"
  exit "$code"
}
trap rollback ERR
echo "Backing up MongoDB locally..."
systemctl start els-mhd-backup.service
[[ "$(systemctl show -p Result --value els-mhd-backup.service)" = success ]] || false
echo "Backing up MongoDB externally..."
systemctl start els-mhd-external-backup.service
[[ "$(systemctl show -p Result --value els-mhd-external-backup.service)" = success ]] || false
echo "Building immutable release-tagged images..."
"${compose[@]}" build api web
echo "Deploying only API/web; DB stays running..."
deployed=1
"${compose[@]}" up -d --no-deps --no-build --force-recreate api web
ok=0
for i in {1..30}; do
  if curl -fsS --max-time 4 http://127.0.0.1:8080/ >/dev/null &&
     curl -fsS --max-time 4 http://127.0.0.1:8080/api/meta >/dev/null; then ok=1; break; fi
  sleep 2
done
[[ "$ok" -eq 1 ]] || { echo "HTTP checks failed" >&2; false; }
install -o root -g root -m 600 "$tmp" "$active_override"
trap - ERR
echo "Release $sha deployed. Active image override: $active_override"
echo "Rollback checkpoint retained: $state"
