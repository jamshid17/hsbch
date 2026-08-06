#!/bin/bash
# Run after deploy to register the Telegram webhook.
set -e

# Load env from backend/.env relative to this script (not the current dir).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
source "${SCRIPT_DIR}/backend/.env"
set +a

curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBAPP_URL}/webhook&secret_token=${TELEGRAM_WEBHOOK_SECRET}"
echo ""
echo "Webhook registered -> ${WEBAPP_URL}/webhook"
