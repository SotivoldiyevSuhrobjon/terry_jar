#!/bin/bash
# Birinchi marta SSL sertifikat olish (Letʼs Encrypt). Serverda bir marta: ./scripts/init-ssl.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
: "${DOMAIN:?DOMAIN .env da yoʼq}"; : "${CERTBOT_EMAIL:?CERTBOT_EMAIL .env da yoʼq}"
live="certbot/conf/live/$DOMAIN"
if [ -f "$live/fullchain.pem" ] && ! grep -q "TERRY-DUMMY" "$live/.dummy" 2>/dev/null; then
  echo "Sertifikat allaqachon bor: $live"; exit 0
fi
mkdir -p "$live" certbot/www
echo "1/4 Vaqtinchalik sertifikat (nginx ishga tushishi uchun)"
openssl req -x509 -nodes -newkey rsa:2048 -days 1 -subj "/CN=$DOMAIN" \
  -keyout "$live/privkey.pem" -out "$live/fullchain.pem" >/dev/null 2>&1
echo TERRY-DUMMY > "$live/.dummy"
echo "2/4 Servislarni ishga tushirish"
docker compose up -d --build web nginx
echo "3/4 Letʼs Encrypt dan sertifikat olish"
rm -rf "certbot/conf/live/$DOMAIN" "certbot/conf/archive/$DOMAIN" "certbot/conf/renewal/$DOMAIN.conf"
docker compose run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" --email "$CERTBOT_EMAIL" --agree-tos --no-eff-email --non-interactive
echo "4/4 nginx ni yangilash"
docker compose exec nginx nginx -s reload
docker compose up -d
echo "Tayyor: https://$DOMAIN"
