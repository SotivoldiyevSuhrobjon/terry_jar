#!/bin/bash
# Zaxiradan tiklash: ./scripts/restore.sh backups/terry_2026-10-25_0230.sql.gz
# DIQQAT: hozirgi bazadagi maʼlumotlar zaxiradagisi bilan almashtiriladi.
set -euo pipefail
cd "$(dirname "$0")/.."
f="${1:?Zaxira fayl yoʼlini bering}"
read -r -p "Baza $f bilan almashtiriladi. Davom etamizmi? (ha/yoʼq) " a
[ "$a" = "ha" ] || exit 1
set -a; . ./.env; set +a
docker compose stop web
docker compose exec -T db psql -U "${POSTGRES_USER:-terry}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-terry}_old;" \
  -c "ALTER DATABASE ${POSTGRES_DB:-terry} RENAME TO ${POSTGRES_DB:-terry}_old;" -c "CREATE DATABASE ${POSTGRES_DB:-terry};"
gunzip -c "$f" | docker compose exec -T db psql -q -U "${POSTGRES_USER:-terry}" -d "${POSTGRES_DB:-terry}"
docker compose start web
echo "Tiklandi. Eski baza ${POSTGRES_DB:-terry}_old nomi bilan saqlab qoʼyildi."
