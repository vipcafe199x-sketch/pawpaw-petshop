#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Engine and the Compose plugin first." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose plugin is not installed." >&2
  exit 1
fi
if [ ! -f .env ]; then
  echo "Copy .env.example to .env and set a strong APP_SECRET, ADMIN_PASSWORD, PUBLIC_BASE_URL and CADDY_SITE." >&2
  exit 1
fi

docker compose up -d --build
docker compose ps
echo "Deployment started. Check https://<your-domain>/api/health and sign in at /admin."
