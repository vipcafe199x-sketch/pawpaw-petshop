#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p backups
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose exec -T app python - "$STAMP" <<'PY'
import sqlite3, sys
from pathlib import Path
stamp=sys.argv[1]
source=sqlite3.connect('/app/data/pawpaw.sqlite3')
target=sqlite3.connect(f'/app/data/backup-{stamp}.sqlite3')
source.backup(target)
target.close(); source.close()
PY
docker compose cp "app:/app/data/backup-${STAMP}.sqlite3" "backups/pawpaw-${STAMP}.sqlite3"
docker compose exec -T app rm -f "/app/data/backup-${STAMP}.sqlite3"
echo "Created backups/pawpaw-${STAMP}.sqlite3. Copy it off the VM and protect it as customer data."
