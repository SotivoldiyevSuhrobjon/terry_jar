#!/bin/sh
# Konteyner ishga tushganda: migratsiya, statik fayllar, keyin ASGI server (HTTP + WebSocket)
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput -v 0
exec uvicorn config.asgi:application \
  --host 0.0.0.0 --port 8000 \
  --workers "${WEB_WORKERS:-3}" \
  --proxy-headers --forwarded-allow-ips="*" \
  --timeout-keep-alive 30 \
  --log-level "${UVICORN_LOG_LEVEL:-warning}"
