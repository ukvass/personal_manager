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

    # CORS: allow specific origins (credentials need explicit origins, not "*")
    CORS_ALLOW_ORIGINS: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        # Add your frontend dev origin(s) here as needed
    ]

    # Security headers toggles
    SECURITY_ENABLE_HSTS: bool = False  # enable in production behind HTTPS
    SECURITY_FRAME_ANCESTORS: str = "'none'"  # deny embedding by default
    # CSP tailored for our stack (htmx from unpkg)
    SECURITY_CSP: str = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
