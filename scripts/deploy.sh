#!/bin/bash
# Yangi versiyani o'rnatish. GitHub Actions avtomatik chaqiradi: ./scripts/deploy.sh <commit>
# Qo'lda ham bo'ladi: ./scripts/deploy.sh   (origin/main)
set -euo pipefail
cd "$(dirname "$0")/.."
REF="${1:-origin/main}"
PREV="$(git rev-parse HEAD)"

echo "==> Kod yangilanmoqda: $REF"
git fetch --quiet origin
git reset --hard "$REF"
export APP_VERSION="$(git rev-parse --short HEAD)"

echo "==> O'rnatishdan oldin baza zaxirasi"
docker compose run --rm --entrypoint sh backup /backup.sh once

echo "==> Obraz yig'ilmoqda ($APP_VERSION)"
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
export APP_VERSION="$(git rev-parse --short HEAD)"
docker compose build web && docker compose up -d
exit 1
