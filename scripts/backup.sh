#!/bin/sh
# Maʼlumotlar bazasining zaxira nusxasi: har kuni 02:30 da ./backups/ ga, KEEP_DAYS kundan eskisi oʼchiriladi.
#   sh backup.sh once  — hozir bitta nusxa
#   sh backup.sh loop  — konteyner ichida har kuni
set -eu
KEEP_DAYS="${KEEP_DAYS:-14}"
dump() {
  f="/backups/terry_$(date +%Y-%m-%d_%H%M).sql.gz"
  pg_dump --no-owner --no-privileges | gzip -9 > "$f.tmp" && mv "$f.tmp" "$f"
  find /backups -name 'terry_*.sql.gz' -mtime +"$KEEP_DAYS" -delete
  echo "$(date '+%F %T') zaxira: $f ($(du -h "$f" | cut -f1))"
}
if [ "${1:-once}" = "once" ]; then dump; exit 0; fi
while :; do
  now=$(date +%s); target=$(date -d "$(date +%F) 02:30" +%s 2>/dev/null || echo $((now + 86400)))
  [ "$target" -le "$now" ] && target=$((target + 86400))
  sleep $((target - now))
  dump || echo "zaxira XATO"
done
