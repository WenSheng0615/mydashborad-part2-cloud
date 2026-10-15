#!/usr/bin/env bash
# Scheduled SQLite backup: publish only a verified snapshot, never an empty final file.
set -euo pipefail
umask 077
PROJECT="${FOCUSFLOW_PROJECT:-/home/wensheng/services/focusflow}"
BACKUP_DIR="${FOCUSFLOW_BACKUP_DIR:-/home/wensheng/backups/focusflow}"
SOURCE="${FOCUSFLOW_DATABASE:-$PROJECT/data/focusflow.db}"
mkdir -p "$BACKUP_DIR"
exec 9>"$BACKUP_DIR/.backup.lock"
flock -n 9 || { echo '[ERROR] Another backup is running' >&2; exit 1; }
STAGING="$(mktemp -d "$BACKUP_DIR/.snapshot-XXXXXX")"
trap 'rm -f -- "$STAGING/snapshot.db"; rmdir -- "$STAGING"' EXIT
DESTINATION="$BACKUP_DIR/focusflow-$(date +%Y%m%d-%H%M%S).db"
echo '[INFO] Creating and verifying SQLite snapshot'
python3 "$PROJECT/scripts/backup_restore.py" "$SOURCE" "$STAGING/snapshot.db"
test -s "$STAGING/snapshot.db"
# Same filesystem, atomic publication; ln refuses an existing destination.
ln -- "$STAGING/snapshot.db" "$DESTINATION"
echo "[OK] Verified backup: $(basename "$DESTINATION")"
