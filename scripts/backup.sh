#!/bin/sh
# Maʼlumotlar bazasining zaxira nusxasi: har kuni 02:30 da ./backups/ ga, KEEP_DAYS kundan eskisi oʼchiriladi.
# TELEGRAM_BOT_TOKEN va TELEGRAM_CHAT_ID berilsa — nusxa Telegram (yopiq kanal/guruh) ga ham yuboriladi;
# BACKUP_PASSPHRASE berilsa — yuborishdan oldin AES-256 bilan shifrlanadi (.enc).
#   sh backup.sh once  — hozir bitta nusxa (+ Telegram)
#   sh backup.sh loop  — konteyner ichida har kuni
set -eu
KEEP_DAYS="${KEEP_DAYS:-14}"
TG_LIMIT="${TG_LIMIT:-47000000}"   # Telegram bot fayl chegarasi ~50 MB; kattasi bo'laklarga bo'linadi

need() {  # alpine konteynerda kerakli dastur bo'lmasa o'rnatadi
  command -v "$1" >/dev/null 2>&1 || apk add --no-cache "$1" >/dev/null 2>&1 || { echo "!! $1 o'rnatilmadi"; return 1; }
}

tg_send() {  # $1 — fayl, $2 — izoh
  curl -fsS --max-time 300 -F chat_id="$TELEGRAM_CHAT_ID" -F caption="$2" -F document=@"$1" \
    "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendDocument" >/dev/null
}

telegram() {
  [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] || return 0
  need curl || return 1
  src="$1"; out="$src"; enc=""
  if [ -n "${BACKUP_PASSPHRASE:-}" ]; then
    need openssl || return 1
    out="/tmp/$(basename "$src").enc"
    openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in "$src" -out "$out" -pass env:BACKUP_PASSPHRASE
    enc=" · shifrlangan"
  fi
  cap="Terry Jar zaxira · $(date '+%d.%m.%Y %H:%M') · $(du -h "$out" | cut -f1)$enc"
  if [ "$(wc -c < "$out")" -gt "$TG_LIMIT" ]; then
    split -b "${TG_PART:-45m}" "$out" "$out.part-"
    n=0; for p in "$out".part-*; do n=$((n + 1)); tg_send "$p" "$cap · bo'lak $n (birlashtirish: cat *.part-* > fayl)"; done
    rm -f "$out".part-*
  else
    tg_send "$out" "$cap"
  fi
  [ "$out" != "$src" ] && rm -f "$out"
  echo "$(date '+%F %T') Telegram'ga yuborildi"
}

dump() {
  f="/backups/terry_$(date +%Y-%m-%d_%H%M).sql.gz"
  pg_dump --no-owner --no-privileges | gzip -9 > "$f.tmp" && mv "$f.tmp" "$f"
  find /backups -name 'terry_*.sql.gz' -mtime +"$KEEP_DAYS" -delete
  echo "$(date '+%F %T') zaxira: $f ($(du -h "$f" | cut -f1))"
  telegram "$f" || echo "!! Telegram'ga yuborib bo'lmadi (zaxira serverda saqlandi)"
}

if [ "${1:-once}" = "once" ]; then dump; exit 0; fi
while :; do
  now=$(date +%s); target=$(date -d "$(date +%F) 02:30" +%s 2>/dev/null || echo $((now + 86400)))
  [ "$target" -le "$now" ] && target=$((target + 86400))
  sleep $((target - now))
  dump || echo "zaxira XATO"
done
