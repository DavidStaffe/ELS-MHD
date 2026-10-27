#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
dir=/opt/els-mhd/rollback
mkdir -p "$dir"
exec 9>"$dir/.lock"
flock -n 9 || { echo "Another deployment operation is running" >&2; exit 1; }
if [[ -e "$dir/current.env" ]]; then
  echo "Rollback checkpoint already exists: $dir/current.env" >&2
  echo "Refusing to overwrite it; retain it until a new release is accepted." >&2
  exit 1
fi
cd /opt/els-mhd/app
[[ -z $(git status --porcelain) ]] || { echo "Git working tree not clean" >&2; exit 1; }
for image in els-mhd-api:latest els-mhd-web:latest; do
  docker image inspect "$image" >/dev/null
done
stamp=$(date +%Y%m%d-%H%M%S)
api_tag="els-mhd-api:rollback-$stamp"
web_tag="els-mhd-web:rollback-$stamp"
docker tag els-mhd-api:latest "$api_tag"
docker tag els-mhd-web:latest "$web_tag"
git_commit=$(git rev-parse HEAD)
{
  printf 'CHECKPOINT=%q\n' "$stamp"
  printf 'GIT_COMMIT=%q\n' "$git_commit"
  printf 'API_IMAGE=%q\n' "$api_tag"
  printf 'WEB_IMAGE=%q\n' "$web_tag"
} > "$dir/current.env"
chmod 600 "$dir/current.env"
echo "Rollback images preserved: $api_tag and $web_tag"
echo "Git commit recorded: $git_commit"
echo "Checkpoint: $dir/current.env"
