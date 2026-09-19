"""Settings the app insists on before it will import.

app.config builds its Settings at module scope and app.db opens an engine
from it, so importing anything under app.services drags in a configuration
the test run has no reason to carry. These are placeholders — nothing here
connects to anything, and setdefault leaves a real local .env alone.
"""

import os

for key, value in {
    "ANTHROPIC_API_KEY": "test",
    "BOT_TOKEN": "1:test",
    "WEBAPP_URL": "https://example.test",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "TELEGRAM_WEBHOOK_SECRET": "test",
}.items():
    os.environ.setdefault(key, value)
