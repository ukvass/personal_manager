# >>> PATCH: app/config.py
# What changed:
# - Pydantic v2 style without deprecated Field(..., env=...) and class Config.
# - Use SettingsConfigDict via pydantic-settings; env vars now map by field name:
#     JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MIN
# - .env поддерживается без устаревших конструкций.

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # JWT settings read from environment (or .env); defaults are safe for dev.
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MIN: int = 60  # access token TTL minutes

    # Database URL (12-factor). Default stays on SQLite for local dev.
    # Examples:
    #   sqlite:///./tasks.db
    #   postgresql+psycopg://user:pass@localhost:5432/personal_manager
    DATABASE_URL: str = "sqlite:///./tasks.db"

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
