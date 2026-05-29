from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    bot_token: str
    webapp_url: str

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
