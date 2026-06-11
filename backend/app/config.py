from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    bot_token: str
    webapp_url: str
    postgres_user: str
    postgres_password: str
    postgres_db: str

    # When true, accept an X-Telegram-User-Id header without initData validation.
    # For local development / browser testing only. Never enable in production.
    dev_allow_unsafe: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
