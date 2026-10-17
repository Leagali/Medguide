from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

CATALOG_URL = (
    "https://www.gov.br/conitec/pt-br/assuntos/avaliacao-de-tecnologias-em-saude/"
    "protocolos-clinicos-e-diretrizes-terapeuticas/pcdt"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDGUIDE_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://medguide:medguide@postgres:5432/medguide"
    redis_url: str = "redis://redis:6379/0"
    admin_token: SecretStr = SecretStr("")
    storage_root: Path = Path("data/raw")
    http_timeout: float = Field(30, gt=0)
    http_attempts: int = Field(3, ge=1, le=5)
    max_download_bytes: int = Field(50 * 1024 * 1024, gt=0)
    max_redirects: int = Field(5, ge=0, le=10)
    request_interval: float = Field(1, ge=0)
    task_attempts: int = Field(2, ge=1, le=10)
    lease_seconds: int = Field(1800, ge=60)
    republish_seconds: int = Field(120, ge=10)
    dispatch_seconds: int = Field(60, ge=10)
    discovery_interval: int = Field(86400, ge=60)
    content_recheck_interval: int = Field(2592000, ge=60)
    user_agent: str = "MedGuide/0.1 (official guideline monitoring; conservative collection)"
    connector_version: str = "conitec-pcdt/1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
