from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    bot_token: str
    webapp_url: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    # When true, accept an X-Telegram-User-Id header without initData validation.
    # For local development / browser testing only. Never enable in production.
    dev_allow_unsafe: bool = False

    # Master switch for the whole paid tier. While false the app is fully
    # free: the scan quota is never spent, the paywall and card block never
    # render, and the admin panel hides its subscription controls. Flipping it
    # back to true restores the existing behaviour untouched — nothing about
    # quotas or payments was deleted, only bypassed.
    subscriptions_enabled: bool = False

    subscription_days: int = 30
    # Lifetime free receipt scans per user (not per day) before a subscription
    # is required. Only enforced while subscriptions_enabled is true.
    free_total_scans: int = 5
    # Comma-separated Telegram user ids that are always admins and can never be
    # demoted from the panel — the bootstrap that keeps the panel reachable.
    # Everyone else is promoted/demoted in-app via bot_users.is_admin.
    admin_telegram_ids: str = ""

    # Receipt upload cap. The Mini App compresses to under 2 MB before
    # uploading, so this is headroom rather than the real limit. Kept in step
    # with `client_max_body_size` on nginx's /api/ location — set higher and
    # nginx rejects the request first, with an HTML 413 the client can't read.
    max_upload_mb: int = 5

    # Manual card payments: the user transfers to this card and sends the
    # receipt to @<admin_contact>, who then enables the subscription by hand.
    # Empty card_number hides the whole card block in the Mini App.
    card_number: str = ""
    card_holder: str = ""
    subscription_price_uzs: int = 0
    admin_contact: str = "hsbchadmin"
    # Must match the secret_token passed to Telegram's setWebhook, and is
    # checked against the X-Telegram-Bot-Api-Secret-Token header on every
    # /webhook request — without it, anyone could POST a forged
    # successful_payment update and grant themselves a free subscription.
    telegram_webhook_secret: str

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def admin_ids(self) -> set[int]:
        return {
            int(part) for part in self.admin_telegram_ids.split(",") if part.strip()
        }

    @property
    def database_url(self) -> str:
        # Derived from POSTGRES_* (single source of truth) so the app's
        # credentials can never drift from what the db container was given.
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
