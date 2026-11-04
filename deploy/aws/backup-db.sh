#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/../.."
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="backups/pawpaw-${STAMP}"
mkdir -p "$DEST/uploads"
cleanup() { docker compose exec -T app rm -f "/app/data/backup-${STAMP}.sqlite3" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker compose exec -T app python - "$STAMP" <<'PY'
import sqlite3, sys
stamp=sys.argv[1]
source=sqlite3.connect('/app/data/pawpaw.sqlite3')
target=sqlite3.connect(f'/app/data/backup-{stamp}.sqlite3')
try:
    source.backup(target)
    if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise RuntimeError('Backup integrity check failed')
finally:
    target.close(); source.close()
PY
docker compose cp "app:/app/data/backup-${STAMP}.sqlite3" "$DEST/pawpaw.sqlite3"
if docker compose exec -T app test -d /app/data/uploads; then
  docker compose cp "app:/app/data/uploads/." "$DEST/uploads"
fi
(cd "$DEST" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
echo "Backup saved to $DEST (SQLite + uploads). Protect, encrypt, and copy off the VM."
echo "For a consistent database/image snapshot, pause writes during backup. Rehearse restoration separately."
