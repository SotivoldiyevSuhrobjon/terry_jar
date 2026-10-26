#!/bin/bash
# Yangi versiyani oʼrnatish. GitHub Actions avtomatik chaqiradi: ./scripts/deploy.sh <commit>
# Qoʼlda ham boʼladi: ./scripts/deploy.sh   (origin/main)
set -euo pipefail
cd "$(dirname "$0")/.."
REF="${1:-origin/main}"
PREV="$(git rev-parse HEAD)"

echo "==> Kod yangilanmoqda: $REF"
git fetch --quiet origin
git reset --hard "$REF"
APP_VERSION="$(git rev-parse --short HEAD)"
export APP_VERSION

echo "==> Oʼrnatishdan oldin baza zaxirasi"
docker compose run --rm --entrypoint sh backup /backup.sh once

echo "==> Obraz yigʼilmoqda ($APP_VERSION)"
docker compose build web
docker compose up -d --remove-orphans

echo "==> Tekshiruv"
for _ in $(seq 1 40); do
  if docker compose exec -T web curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then
    echo "OK: $APP_VERSION ishlayapti"
    docker image prune -f --filter "until=168h" >/dev/null
    exit 0
  fi
  sleep 3
done

echo "!! Yangi versiya ishga tushmadi — oldingisiga qaytarilmoqda ($PREV)"
git reset --hard "$PREV"
APP_VERSION="$(git rev-parse --short HEAD)"
export APP_VERSION
docker compose build web && docker compose up -d
exit 1
