#!/bin/bash
# Zaxiradan tiklash:
#   ./scripts/restore.sh backups/terry_2026-10-25_0230.sql.gz
#   ./scripts/restore.sh terry_2026-10-25_0230.sql.gz.enc      (Telegram'dan olingan shifrlangan nusxa)
# DIQQAT: hozirgi bazadagi maʼlumotlar zaxiradagisi bilan almashtiriladi (eskisi _old nomi bilan qoladi).
set -euo pipefail
cd "$(dirname "$0")/.."
f="${1:?Zaxira fayl yoʼlini bering}"
set -a; . ./.env; set +a
src="$f"
if [[ "$f" == *.enc ]]; then
  pass="${BACKUP_PASSPHRASE:-}"
  [ -n "$pass" ] || { read -r -s -p "Shifrlash paroli (BACKUP_PASSPHRASE): " pass; echo; }
  src="$(mktemp)"; trap 'rm -f "$src"' EXIT
  BACKUP_PASSPHRASE="$pass" openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in "$f" -out "$src" -pass env:BACKUP_PASSPHRASE
  echo "Shifr ochildi."
fi
gzip -t "$src" || { echo "!! Fayl buzilgan yoki parol notoʼgʼri"; exit 1; }
read -r -p "Baza $f bilan almashtiriladi. Davom etamizmi? (ha/yoʼq) " a
[ "$a" = "ha" ] || exit 1
docker compose stop web
docker compose exec -T db psql -U "${POSTGRES_USER:-terry}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-terry}_old;" \
  -c "ALTER DATABASE ${POSTGRES_DB:-terry} RENAME TO ${POSTGRES_DB:-terry}_old;" -c "CREATE DATABASE ${POSTGRES_DB:-terry};"
gunzip -c "$src" | docker compose exec -T db psql -q -U "${POSTGRES_USER:-terry}" -d "${POSTGRES_DB:-terry}"
docker compose start web
echo "Tiklandi. Eski baza ${POSTGRES_DB:-terry}_old nomi bilan saqlab qoʼyildi."
