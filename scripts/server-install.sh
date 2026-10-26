#!/bin/bash
# Terry Jar — nginx allaqachon ishlayotgan serverga subdomen bilan oʼrnatish (bir marta).
#
#   (oldin kompyuterdan: scp core\fixtures\staff.json root@SERVER_IP:/root/staff.json)
#   curl -fsSL https://raw.githubusercontent.com/SotivoldiyevSuhrobjon/terry_jar/main/scripts/server-install.sh -o install.sh
#   sudo bash install.sh terryjar.duckdns.org siz@gmail.com            # toza holat
#   sudo bash install.sh terryjar.duckdns.org siz@gmail.com --demo     # demo sinov maʼlumotlari bilan
#
# Nima qiladi: Docker (yoʼq boʼlsa) → kod /opt/terry_jar → .env (maxfiy kalitlar avtomatik) → konteynerlar
# → boshlangʼich maʼlumot va xodimlar → host nginxʼga subdomen → Letʼs Encrypt SSL.
# Boshqa saytlarga (masalan Taskflow) va ularning nginx sozlamalariga tegmaydi.
set -euo pipefail

DOMAIN="${1:-}"; EMAIL="${2:-}"; MODE="${3:-}"
REPO="${REPO:-https://github.com/SotivoldiyevSuhrobjon/terry_jar.git}"
DIR="${DIR:-/opt/terry_jar}"
[ -n "$DOMAIN" ] && [ -n "$EMAIL" ] || { echo "Ishlatish: sudo bash install.sh SUBDOMEN EMAIL [--demo]"; exit 1; }
[ "$(id -u)" = 0 ] || { echo "root sifatida ishga tushiring (sudo)"; exit 1; }

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
rand() { head -c 600 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | cut -c1-"$1"; }  # SIGPIPEsiz (pipefail bilan xavfsiz)

say "0/8 Tekshiruv"
IP_DNS="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)"
IP_ME="$(curl -fsS -4 --max-time 5 https://api.ipify.org || true)"
echo "DNS: $DOMAIN -> ${IP_DNS:-?}   Server IP: ${IP_ME:-?}"
if [ -n "$IP_DNS" ] && [ -n "$IP_ME" ] && [ "$IP_DNS" != "$IP_ME" ]; then
  echo "!! Subdomen boshqa IP ga qaragan. DuckDNSʼda IP ni $IP_ME qiling va qayta ishga tushiring."; exit 1
fi
command -v nginx >/dev/null || { echo "!! Serverda nginx topilmadi. Bu skript mavjud nginx uchun. DEPLOY.md «A» rejimiga qarang."; exit 1; }
free -m | awk '/Mem:/{print "RAM: "$2" MB, ishlatilmagan: "$7" MB"}'; df -h / | awk 'NR==2{print "Disk: "$4" ishlatilmagan"}'

say "1/8 Docker"
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sh; fi
docker compose version

say "2/8 Kod: $DIR"
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull --ff-only; else git clone "$REPO" "$DIR"; fi
cd "$DIR"

say "3/8 Sozlamalar (.env)"
port_busy() { if command -v ss >/dev/null; then ss -ltn | awk '{print $4}' | grep -q ":$1\$"; else (echo >"/dev/tcp/127.0.0.1/$1") 2>/dev/null; fi; }
PORT=8010; while port_busy "$PORT"; do PORT=$((PORT+1)); done
if [ ! -f .env ]; then
  ADMIN_PATH="boshqaruv-$(rand 8 | tr 'A-Z' 'a-z')/"
  cat > .env <<EOF
COMPOSE_PROFILES=
WEB_PORT=$PORT
DOMAIN=$DOMAIN
CERTBOT_EMAIL=$EMAIL
DJANGO_SECRET_KEY=$(rand 60)
DJANGO_ALLOWED_HOSTS=$DOMAIN
DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN
DJANGO_ADMIN_URL=$ADMIN_PATH
DJANGO_DEBUG=0
POSTGRES_DB=terry
POSTGRES_USER=terry
POSTGRES_PASSWORD=$(rand 32)
ADMIN_USERNAME=admin
ADMIN_FULL_NAME=Administrator
ADMIN_PASSWORD=
WEB_WORKERS=2
SESSION_HOURS=16
BACKUP_KEEP_DAYS=14
EOF
  chmod 600 .env
  echo ".env yaratildi (port $PORT)"
else
  echo ".env bor — oʼzgartirilmadi"; PORT="$(grep -E '^WEB_PORT=' .env | cut -d= -f2)"; PORT="${PORT:-8010}"
fi

STAFF_SRC="${STAFF:-/root/staff.json}"
if [ ! -f core/fixtures/staff.json ] && [ -f "$STAFF_SRC" ]; then cp "$STAFF_SRC" core/fixtures/staff.json; fi
if [ ! -f core/fixtures/staff.json ]; then
  echo "!! Xodimlar roʼyxati yoʼq. Kompyuteringizdan (PowerShell, loyiha papkasida) yuklang:"
  echo "   scp core\\fixtures\\staff.json root@SERVER_IP:/root/staff.json"
  echo "   soʼng skriptni qayta ishga tushiring."; exit 1
fi

say "4/8 Konteynerlar (birinchi marta 3-5 daqiqa)"
docker compose up -d --build
for _ in $(seq 1 60); do curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break; sleep 3; done
curl -fsS "http://127.0.0.1:$PORT/healthz" && echo

say "5/8 Boshlangʼich maʼlumot"
if [ "$MODE" = "--demo" ]; then docker compose exec -T web python manage.py init_state --demo
else docker compose exec -T web python manage.py init_state; fi

say "6/8 Xodimlar (vaqtinchalik parollar pastda — saqlab oling!)"
docker compose exec -T web python manage.py init_users

say "7/8 nginx: $DOMAIN -> 127.0.0.1:$PORT"
SITE=/etc/nginx/sites-available/terryjar
if [ -d /etc/nginx/sites-available ]; then
  sed -e "s/SUBDOMEN/$DOMAIN/g" -e "s/127.0.0.1:8010/127.0.0.1:$PORT/g" nginx/host-site.conf.example > "$SITE"
  ln -sf "$SITE" /etc/nginx/sites-enabled/terryjar
else
  SITE=/etc/nginx/conf.d/terryjar.conf
  sed -e "s/SUBDOMEN/$DOMAIN/g" -e "s/127.0.0.1:8010/127.0.0.1:$PORT/g" nginx/host-site.conf.example > "$SITE"
fi
nginx -t && systemctl reload nginx

say "8/8 SSL (Letʼs Encrypt)"
command -v certbot >/dev/null || { apt-get update -qq && apt-get install -y -qq certbot python3-certbot-nginx; }
certbot --nginx -d "$DOMAIN" -m "$EMAIL" --agree-tos --no-eff-email --non-interactive --redirect

echo
curl -fsS "https://$DOMAIN/healthz" && echo
cat <<EOF

TAYYOR:  https://$DOMAIN
Admin panel:  https://$DOMAIN/$(grep -E '^DJANGO_ADMIN_URL=' .env | cut -d= -f2)
Parollar nusxasi:  docker compose exec web cat /app/data/boshlangich_parollar.txt
(tarqatgach: docker compose exec web rm /app/data/boshlangich_parollar.txt)
Yangilash:  cd $DIR && ./scripts/deploy.sh
EOF
