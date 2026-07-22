#!/bin/sh
set -e

cd /app

mkdir -p /app/strategies /app/logs /app/alerts

# Host may mount an empty alerts volume — seed an empty list if missing
if [ ! -f /app/alerts/alerts.json ]; then
  echo '[]' > /app/alerts/alerts.json
fi

# Optional .env: prefer mounted file; otherwise copy example so dotenv does not fail hard
if [ ! -f /app/.env ] && [ -f /app/.env.example ]; then
  echo "No .env found — copying .env.example (fill Trading212 / Telegram keys as needed)"
  cp /app/.env.example /app/.env
fi

exec "$@"
