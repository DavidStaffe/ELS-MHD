#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ ! -f /opt/els-mhd/update-state/active.json ]] || { echo "Host-agent installation: use System & Updates; legacy rollback is disabled" >&2; exit 1; }
[[ $EUID -eq 0 ]] || exit 1
cd /opt/els-mhd/app
exec 9>/opt/els-mhd/rollback/.deploy.lock
flock -n 9 || exit 1
source /opt/els-mhd/rollback/current.env
[[ "$CHECKPOINT" =~ ^[0-9]{8}-[0-9]{6}$ ]] || exit 1
[[ "$API_IMAGE" == "els-mhd-api:rollback-$CHECKPOINT" ]] || exit 1
[[ "$WEB_IMAGE" == "els-mhd-web:rollback-$CHECKPOINT" ]] || exit 1
docker image inspect "$API_IMAGE" "$WEB_IMAGE" >/dev/null
saved_compose="/opt/els-mhd/rollback/compose-$CHECKPOINT.yaml"
[[ -f "$saved_compose" ]] || { echo "Missing saved Compose" >&2; exit 1; }
tmp=$(mktemp /opt/els-mhd/rollback/.rollback-XXXXXXXX.yaml)
trap 'rm -f "$tmp"' EXIT
printf 'services:\n  api:\n    image: %s\n  web:\n    image: %s\n' "$API_IMAGE" "$WEB_IMAGE" > "$tmp"
docker compose --project-directory /opt/els-mhd/app/deploy --env-file /opt/els-mhd/config/docker.env -f "$saved_compose" -f "$tmp" config --quiet
docker compose --project-directory /opt/els-mhd/app/deploy --env-file /opt/els-mhd/config/docker.env -f "$saved_compose" -f "$tmp" up -d --no-deps --no-build --force-recreate api web
install -o root -g root -m 600 "$tmp" /opt/els-mhd/rollback/active-images.compose.yaml
echo "Pinned rollback images restored; database unchanged"
