from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 30
    email_verification_token_expire_hours: int = 24
    frontend_url: str = "http://localhost:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@sec.local"
    smtp_use_tls: bool = True
    pawapay_base_url: str = "https://api.sandbox.pawapay.io"
    pawapay_api_token: str | None = None
    pawapay_callback_url: str | None = None
    pawapay_default_country: str = "COD"
    pawapay_default_currency: str = "CDF"
    pawapay_default_correspondent: str | None = None
    firebase_credentials_path: str | None = None
    firebase_project_id: str | None = None
    meter_sync_secret: str | None = None
    first_admin_email: str = "admin@sec.local"
    first_admin_password: str = "admin12345"
    first_admin_full_name: str = "SEC Admin"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
