"""Application settings loaded from environment variables via pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "nodues_db"
    POSTGRES_USER: str = "nodues_user"
    POSTGRES_PASSWORD: str = "changeme"

    # App
    APP_ENV: str = "development"

    # Seed
    SEED_DEFAULT_PASSWORD: str = "changeme_seed"

    # JWT Authentication (JWT_SECRET has no default; app refuses to start if missing)
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS & Security
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    ALLOWED_EMAIL_DOMAINS: str = "example.edu"

    # Email & OTP
    MAIL_CONSOLE_ONLY: bool = True
    DEV_RETURN_OTP: bool = False

    # Swagger / OpenAPI Docs
    ENABLE_DOCS: bool = True

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_email_domain_list(self) -> list[str]:
        return [d.strip().lower() for d in self.ALLOWED_EMAIL_DOMAINS.split(",") if d.strip()]


settings = Settings()
