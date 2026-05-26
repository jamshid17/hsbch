#!/bin/bash
# Run after deploy to register the Telegram webhook
set -e
source .env
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBAPP_URL}/webhook"
echo ""
echo "Webhook registered."
