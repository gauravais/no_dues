"""Application settings loaded from environment variables via pydantic-settings."""
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(raw_url: str) -> str:
    """
    Normalise database URL for SQLAlchemy+psycopg:
    - Normalises postgres:// and postgresql:// to postgresql+psycopg://
    - Enforces sslmode=require if the database host is not local.
    """
    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    is_local = hostname in ("localhost", "127.0.0.1", "nodues_db", "test_db") or not hostname

    query_params = parse_qs(parsed.query, keep_blank_values=True)
    if not is_local:
        if "sslmode" not in query_params:
            query_params["sslmode"] = ["require"]

    new_query = urlencode(query_params, doseq=True)
    new_parts = list(parsed)
    new_parts[4] = new_query
    return urlunparse(new_parts)


def assert_local_test_database(url: str) -> None:
    """Security guard ensuring automated tests never run against a remote database (e.g. Neon)."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    allowed_hosts = {"localhost", "127.0.0.1", "nodues_db", "test_db"}
    if hostname not in allowed_hosts:
        raise RuntimeError(
            f"SECURITY GUARD: Test database host '{hostname}' is not allowed! "
            f"Tests must only run on local databases ({', '.join(sorted(allowed_hosts))}). "
            f"Never run tests against a remote database such as Neon."
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database: support single DATABASE_URL with POSTGRES_* as local fallback
    RAW_DATABASE_URL: str | None = Field(default=None, validation_alias="DATABASE_URL")
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "nodues_db"
    POSTGRES_USER: str = "nodues_user"
    POSTGRES_PASSWORD: str = "changeme"

    # App
    APP_ENV: str = "development"

    # Seed
    SEED_DEFAULT_PASSWORD: str = "changeme_seed"
    SEED_STAFF_EMAIL_DOMAIN: str = "svsu.ac.in"

    # JWT Authentication (JWT_SECRET has no default; app refuses to start if missing)
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS & Security
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    ALLOWED_EMAIL_DOMAINS: str = "example.edu"
    TRUST_PROXY_HEADERS: bool = True
    TRUSTED_CLIENT_IP_HEADER: str = ""

    # Email & Outbox (console | smtp | brevo | resend | disabled)
    EMAIL_BACKEND: str | None = None
    BREVO_API_KEY: str | None = None
    RESEND_API_KEY: str | None = None
    EMAIL_FROM: str | None = None
    MAIL_CONSOLE_ONLY: bool = True
    DEV_RETURN_OTP: bool = False

    # SMTP Settings (Used when EMAIL_BACKEND=smtp)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    SMTP_USE_TLS: bool = True
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    EMAIL_ALLOWLIST: str = ""
    REMINDERS_ENABLED: bool = False
    REMINDER_AFTER_DAYS: int = 3

    # Scheduled Jobs Secret (X-Job-Key protection for /internal/jobs/*)
    JOB_SECRET: str | None = None

    # Swagger / OpenAPI Docs
    ENABLE_DOCS: bool = True

    # Public Verification & Certificate QR Base URL
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Bank Data Encryption Key (Fernet 32-byte key; required in production/development)
    BANK_DATA_KEY: str | None = None

    # Google Authentication & Login Gate Flags
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_ALLOWED_DOMAINS: str | None = None
    AUTH_OTP_SIGNUP_ENABLED: bool = False
    AUTH_PASSWORD_LOGIN_FOR_STUDENTS: bool = False

    @model_validator(mode="after")
    def validate_production_and_security(self) -> "Settings":
        if self.APP_ENV != "test" and not self.BANK_DATA_KEY:
            raise ValueError("BANK_DATA_KEY environment variable is required")

        if self.APP_ENV == "production":
            if not self.JWT_SECRET or len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if self.DEV_RETURN_OTP is True:
                raise ValueError("DEV_RETURN_OTP must be False in production")
            if self.MAIL_CONSOLE_ONLY is True:
                raise ValueError("MAIL_CONSOLE_ONLY must be False in production")
            if not self.BANK_DATA_KEY:
                raise ValueError("BANK_DATA_KEY is missing in production")
            if self.ENABLE_DOCS is True:
                raise ValueError("ENABLE_DOCS must be False in production")
            if any("localhost" in origin.lower() for origin in self.cors_origin_list):
                raise ValueError("CORS_ORIGINS must not contain localhost in production")
            if not self.FRONTEND_BASE_URL.startswith("https://"):
                raise ValueError("FRONTEND_BASE_URL must use https:// in production")
            if not self.google_enabled and not self.AUTH_OTP_SIGNUP_ENABLED:
                raise ValueError("GOOGLE_CLIENT_ID must be set in production unless AUTH_OTP_SIGNUP_ENABLED is True")
            if self.AUTH_PASSWORD_LOGIN_FOR_STUDENTS is True:
                raise ValueError("AUTH_PASSWORD_LOGIN_FOR_STUDENTS must be False in production")

            # Email backend guards in production
            backend = self.email_backend
            if backend == "console":
                raise ValueError("EMAIL_BACKEND='console' is not allowed in production")
            elif backend == "smtp":
                if not self.SMTP_HOST or not self.SMTP_PORT or not (self.SMTP_FROM or self.EMAIL_FROM):
                    raise ValueError("SMTP_HOST, SMTP_PORT, and SMTP_FROM/EMAIL_FROM are required when EMAIL_BACKEND='smtp'")
            elif backend == "brevo":
                if not self.BREVO_API_KEY or not (self.EMAIL_FROM or self.SMTP_FROM):
                    raise ValueError("BREVO_API_KEY and EMAIL_FROM are required when EMAIL_BACKEND='brevo'")
            elif backend == "resend":
                if not self.RESEND_API_KEY or not (self.EMAIL_FROM or self.SMTP_FROM):
                    raise ValueError("RESEND_API_KEY and EMAIL_FROM are required when EMAIL_BACKEND='resend'")
            elif backend != "disabled":
                raise ValueError(
                    f"Invalid EMAIL_BACKEND '{backend}'. Must be one of: console, smtp, brevo, resend, disabled"
                )
        return self

    def get_bank_data_key(self) -> str:
        if self.BANK_DATA_KEY:
            return self.BANK_DATA_KEY
        # Fallback test key for test environment
        return "9VgS5iI8WKkmZC3Irsvriq4CkX1OLKU4eHXp0DiwynA="

    @property
    def DATABASE_URL(self) -> str:
        if self.RAW_DATABASE_URL and self.RAW_DATABASE_URL.strip():
            return normalize_database_url(self.RAW_DATABASE_URL)
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def email_backend(self) -> str:
        if self.EMAIL_BACKEND and self.EMAIL_BACKEND.strip():
            return self.EMAIL_BACKEND.strip().lower()
        return "disabled" if self.APP_ENV == "production" else "console"

    @property
    def email_from_address(self) -> str:
        return self.EMAIL_FROM or self.SMTP_FROM or "noreply@svsu.ac.in"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_email_domain_list(self) -> list[str]:
        return [d.strip().lower() for d in self.ALLOWED_EMAIL_DOMAINS.split(",") if d.strip()]

    @property
    def email_allowlist_set(self) -> set[str]:
        if not self.EMAIL_ALLOWLIST or not self.EMAIL_ALLOWLIST.strip():
            return set()
        return {e.strip().lower() for e in self.EMAIL_ALLOWLIST.split(",") if e.strip()}

    @property
    def google_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_ID.strip())

    @property
    def google_allowed_domain_list(self) -> list[str]:
        if self.GOOGLE_ALLOWED_DOMAINS and self.GOOGLE_ALLOWED_DOMAINS.strip():
            return [d.strip().lower() for d in self.GOOGLE_ALLOWED_DOMAINS.split(",") if d.strip()]
        return self.allowed_email_domain_list


settings = Settings()
