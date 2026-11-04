#!/usr/bin/env bash
set -euo pipefail
root="${PAWPAW_ROOT:-/opt/pawpaw}"
image="pawpaw-candidate-${GITHUB_SHA:-local}"
public_health="${PAWPAW_HEALTH_URL:-https://pawpaw-petshop.mooo.com/api/health}"
if docker inspect pawpaw-rollback >/dev/null 2>&1; then
  echo 'Existing rollback container; inspect it before deployment.' >&2
  exit 1
fi
docker inspect pawpaw >/dev/null
docker build -t "$image" "$root"
docker stop pawpaw >/dev/null
renamed=0
rollback() {
  local rc=$?
  trap - ERR INT TERM
  echo 'Deploy failed; attempting to restart previous container. Database backup remains on the data volume.' >&2
  if [ "$renamed" = 1 ]; then
    docker rm -f pawpaw >/dev/null 2>&1 || true
    docker rename pawpaw-rollback pawpaw || { echo 'Rollback rename failed; manual intervention required.' >&2; exit 1; }
  fi
  docker start pawpaw >/dev/null || { echo 'Rollback start failed; manual intervention required.' >&2; exit 1; }
  exit "$rc"
}
trap rollback ERR INT TERM
# Guard writes a SQLite backup before checking/applying migrations. Never restore automatically.
docker run --rm --network none --env-file "$root/.env" -v pawpaw-data:/app/data "$image" python -m backend.deployment_guard --data-root /app/data
docker rename pawpaw pawpaw-rollback
renamed=1
docker run -d --restart unless-stopped --name pawpaw -p 127.0.0.1:8001:8000 --env-file "$root/.env" -v pawpaw-data:/app/data "$image" >/dev/null
ready=0
for _ in $(seq 1 20); do
  if curl -fsS --max-time 5 http://127.0.0.1:8001/api/health >/dev/null; then ready=1; break; fi
  sleep 2
done
[ "$ready" = 1 ]
curl -fsS --max-time 10 "$public_health" >/dev/null
docker tag "$image" pawpaw-petshop
trap - ERR INT TERM
docker rm pawpaw-rollback >/dev/null || echo 'Warning: previous stopped container could not be removed.' >&2
echo 'Deployment health checks passed; pre-deploy database backup retained.'
