#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

MOUNT=/mnt/els-mhd-backup
UUID=76000f5f-4e3c-4ff5-9ea1-45ec50f2668a
REPOSITORY="$MOUNT/restic-els-mhd"
PASSWORD_FILE=/opt/els-mhd/config/restic-password
SOURCE=/opt/els-mhd/backups

if ! mountpoint -q "$MOUNT"; then
  echo "ERROR: external backup disk is not mounted" >&2
  exit 1
fi
actual_uuid=$(findmnt -n -o UUID --mountpoint "$MOUNT")
if [[ "$actual_uuid" != "$UUID" ]]; then
  echo "ERROR: mounted disk UUID mismatch" >&2
  exit 1
fi
[[ -s "$PASSWORD_FILE" ]] || { echo "ERROR: missing restic password file" >&2; exit 1; }
[[ -d "$REPOSITORY/config" ]] || { echo "ERROR: missing initialized restic repository" >&2; exit 1; }
[[ -d "$SOURCE" ]] || { echo "ERROR: missing local backup directory" >&2; exit 1; }
# Only copy after a successful local backup, never export stale archives silently.
latest=$(find "$SOURCE" -maxdepth 1 -type f -name 'els-mhd-????????-??????.archive.gz' -printf '%T@ %p\n' | sort -nr | head -n 1)
[[ -n "$latest" ]] || { echo "ERROR: no MongoDB archive found" >&2; exit 1; }
latest_file=${latest#* }
[[ -s "$latest_file" ]] || { echo "ERROR: latest MongoDB archive is empty" >&2; exit 1; }

export RESTIC_REPOSITORY="$REPOSITORY"
export RESTIC_PASSWORD_FILE="$PASSWORD_FILE"

echo "Starting external encrypted backup"
restic backup "$SOURCE" --tag els-mhd --exclude '.backup.lock' --exclude '*.partial'
echo "Checking restic repository integrity"
restic check
echo "Applying snapshot retention (14 daily / 8 weekly / 12 monthly)"
restic forget --tag els-mhd --keep-daily 14 --keep-weekly 8 --keep-monthly 12 --prune
echo "External backup completed"
