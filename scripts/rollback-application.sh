#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || exit 1
cd /opt/els-mhd/app
exec 9>/opt/els-mhd/rollback/.deploy.lock
flock -n 9 || exit 1
source /opt/els-mhd/rollback/current.env
[[ "$API_IMAGE" =~ ^els-mhd-api:rollback-[0-9]{8}-[0-9]{6}$ ]] || exit 1
[[ "$WEB_IMAGE" =~ ^els-mhd-web:rollback-[0-9]{8}-[0-9]{6}$ ]] || exit 1
docker image inspect "$API_IMAGE" "$WEB_IMAGE" >/dev/null
docker tag "$API_IMAGE" els-mhd-api:latest
docker tag "$WEB_IMAGE" els-mhd-web:latest
docker compose --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml up -d --no-build --force-recreate api web
echo "Previous images restored; MongoDB data unchanged"
