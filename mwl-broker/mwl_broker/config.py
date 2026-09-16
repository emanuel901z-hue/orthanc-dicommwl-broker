"""Runtime configuration via environment variables (prefix BROKER_)."""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Postgres — own database "mwl" on the shared index-DB instance
    database_url: str = "postgresql+psycopg://dev:dev@postgres:5432/mwl"

    # DICOM SCP identity — what modalities see
    broker_aet: str = "MWLBROKER"
    dicom_port: int = 11113
    max_associations: int = 20

    # Upstream C-FIND fan-out
    upstream_timeout_s: int = 10

    # Echo monitoring loop
    echo_interval_s: int = 30

    # Store routing
    strict_store_status: bool = True  # report DIMSE error to modality when forward fails
    seen_item_ttl_days: int = 30

    # Restrict which calling AETs may query/store (empty = allow all)
    allowed_calling_aets: str = ""  # comma-separated

    # Local dev convenience: skip DICOM SCP + echo loop (tests)
    start_dicom: bool = True
    start_echo_loop: bool = True

    # Optional bootstrap: JSON list of sources/targets to upsert on startup
    seed_config_json: str = ""

    model_config = {"env_prefix": "BROKER_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
