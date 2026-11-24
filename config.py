
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AbbiKayGa"
    debug: bool = False

    # Existing PostgreSQL settings
    database_username: str
    database_password: str
    database_hostname: str
    database_port: str
    database_name: str

    # Existing authentication settings
    admin_secret_key: str
    customer_secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Initial administrator settings
    bootstrap_admin_email: str | None = None
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
