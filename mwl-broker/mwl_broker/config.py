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

    # Config audit: header that carries the operator identity (empty = "api")
    audit_actor_header: str = "X-OE3-User"

    # Worklist cache (outage bridge) — conservative defaults
    cache_enabled: bool = True          # serve cached answers when a source fails
    cache_stale_max_s: int = 120        # hard cap for stale serving (0 = never)
    cache_hide_completed: bool = True   # never resurrect COMPLETED/DISCONTINUED steps
    cache_max_items: int = 5000         # safety cap per source snapshot

    # C-STORE spool (store and forward) — never lose an image
    spool_enabled: bool = True
    accept_when_queued: bool = True     # ack the modality once the instance is safely spooled
    spool_dir: str = "/var/lib/mwl-broker/spool"
    spool_max_items: int = 20000        # capacity guard (queued + failed + dead)
    spool_max_bytes: int = 10737418240  # 10 GiB
    spool_max_attempts: int = 10        # then the entry becomes a dead letter
    spool_backoff_s: int = 60           # base for the exponential retry backoff
    spool_retention_s: int = 86400      # how long a sent entry stays as a duplicate guard
    spool_poll_s: int = 10              # retry worker interval

    # Circuit breaker per upstream source (C-FIND fan-out)
    breaker_fail_threshold: int = 3   # consecutive failures before opening
    breaker_open_seconds: int = 60    # how long an open breaker stays open

    # Local dev convenience: skip DICOM SCP + echo loop (tests)
    start_dicom: bool = True
    start_echo_loop: bool = True
    start_spool: bool = True

    # Optional bootstrap: JSON list of sources/targets to upsert on startup
    seed_config_json: str = ""

    model_config = {"env_prefix": "BROKER_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
