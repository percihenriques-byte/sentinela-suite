from functools import lru_cache
from typing import Annotated, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_env: str = "dev"
    app_secret_key: str = "dev-insecure-change-me"
    database_url: str = "sqlite:///./jarvis_crm.db"

    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    # (Removed: anthropic_* config — local-only assistant per user rule)

    # `NoDecode` tells pydantic-settings NOT to JSON-parse the raw env string,
    # so our @field_validator gets to see the comma-separated form (previously
    # pydantic-settings 2.x tried json.loads first, blew up on plain strings,
    # and never called our validator).
    cors_origins: Annotated[List[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])
    field_encryption_key: str = ""

    rate_limit_enabled: bool = True
    # Optional periodic backup of all workspaces to disk.
    # If set, writes JSON envelopes to the directory every backup_interval_minutes.
    jarvis_backup_dir: str = ""
    backup_interval_minutes: int = 60

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            parts = [o.strip() for o in v.split(",") if o.strip()]
            # If the env var is set but empty (or only whitespace/commas), fall
            # back to the localhost default instead of an empty list — an empty
            # allow list would break CORS silently in dev.
            return parts or ["http://localhost:3000"]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
