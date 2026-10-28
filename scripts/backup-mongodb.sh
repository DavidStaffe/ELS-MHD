#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BACKUP_DIR=/opt/els-mhd/backups
DB_CONTAINER=els-mhd-db-1
RETENTION_DAYS=14

install -d -m 0700 "$BACKUP_DIR"
exec 9>"$BACKUP_DIR/.backup.lock"
flock -n 9 || { echo "Another backup is running" >&2; exit 1; }

stamp=$(date +%Y%m%d-%H%M%S)
destination="$BACKUP_DIR/els-mhd-$stamp.archive.gz"
tempfile=$(mktemp "$BACKUP_DIR/.els-mhd-$stamp.XXXXXXXX.partial")
trap 'rm -f -- "$tempfile"' EXIT

echo "Starting ELS-MHD MongoDB backup ($stamp)"
docker exec "$DB_CONTAINER" sh -c '
  exec mongodump \
    --username "$MONGO_INITDB_ROOT_USERNAME" \
    --password "$MONGO_INITDB_ROOT_PASSWORD" \
    --authenticationDatabase admin \
    --db els_mhd \
    --archive \
    --gzip
' > "$tempfile"

test -s "$tempfile" || { echo "Backup is empty" >&2; exit 1; }
chmod 0600 "$tempfile"
mv -n -- "$tempfile" "$destination"
echo "Backup created: $destination ($(stat -c '%s' "$destination") bytes)"

# Remove only backups matching this script's filename pattern, after success.
find "$BACKUP_DIR" -maxdepth 1 -type f \
  -name 'els-mhd-????????-??????.archive.gz' -mtime +13 -delete
echo "Backup completed"
