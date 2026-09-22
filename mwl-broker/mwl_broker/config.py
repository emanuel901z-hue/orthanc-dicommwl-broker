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
    # worklist preview: PHI-free by default, patient name/ID only when switched on
    simulate_show_phi: bool = False
    # keep the raw HL7 message (PHI) for troubleshooting and replay
    hl7_store_raw: bool = False
    # MPPS: accept performed procedure steps and report them back to the RIS
    mpps_enabled: bool = True
    mpps_forward_enabled: bool = False
    mpps_forward_transport: str = "mllp"
    mpps_forward_host: str = ""
    mpps_forward_port: int = 2575
    mpps_forward_url: str = ""
    mpps_hide_completed: bool = True
    cache_stale_max_s: int = 120        # hard cap for stale serving (0 = never)
    cache_hide_completed: bool = True   # never resurrect COMPLETED/DISCONTINUED steps
    cache_max_items: int = 5000         # safety cap per source snapshot

    # DICOM TLS — off by default, per direction; plain and TLS can coexist
    tls_inbound_enabled: bool = False   # the listener the modalities connect to
    tls_inbound_port: int = 2762        # the usual DICOM TLS port
    tls_inbound_cert_file: str = ""
    tls_inbound_key_file: str = ""
    tls_inbound_ca_file: str = ""       # needed for mTLS (client authentication)
    tls_inbound_client_auth: str = "none"   # none | optional | required (mTLS)
    tls_outbound_ca_file: str = ""      # trust anchor for RIS/PACS (empty = system store)
    tls_outbound_client_cert_file: str = ""  # the broker's identity for mTLS
    tls_outbound_client_key_file: str = ""
    tls_outbound_verify: bool = True    # verify remote certificates by default
    tls_dir: str = "/var/lib/mwl-broker/tls"   # managed certificates

    # Locally maintained worklist items (emergencies, unscheduled exams)
    local_priority: int = -1            # merge priority: before every upstream source
    local_default_validity_days: int = 7   # 0 = items never expire

    # HL7 ORM interface
    hl7_enabled: bool = True            # accept POST /hl7/orm
    hl7_mllp_enabled: bool = False      # extra MLLP listener for the RIS
    hl7_mllp_bind: str = "0.0.0.0"
    hl7_mllp_port: int = 2575
    hl7_default_station_aet: str = ""   # fallback when the ORM carries none
    hl7_default_modality: str = ""

    # IHE ATNA audit trail (own Audit Record Repository)
    atna_enabled: bool = False          # explicit opt-in: audit leaves the broker
    atna_syslog_host: str = ""
    atna_syslog_port: int = 6514
    atna_syslog_protocol: str = "tcp"   # tcp | tls
    atna_tls_ca_file: str = ""          # optional CA bundle for TLS
    atna_queue_max: int = 10000         # bounded buffer against a dead ARR

    # RBAC: the proxy authenticates and injects the roles; the broker decides
    # read vs. write. Off by default — a single-admin setup works unchanged.
    rbac_mode: str = "off"              # off | enforce
    rbac_roles_header: str = "X-OE3-Roles"
    rbac_write_role: str = "brokerWrite"

    # Retention (days; 0 = keep forever) — see GET /retention
    retention_query_log_days: int = 90
    retention_store_log_days: int = 180
    retention_mpps_days: int = 365
    retention_hl7_days: int = 30
    retention_local_items_days: int = 0     # the items carry their own validity
    retention_spool_days: int = 7           # delivered + dead entries
    retention_config_audit_days: int = 0    # the accounting trail: keep forever

    # Locally maintained worklist items (emergencies, unscheduled exams)
    notify_webhook_url: str = ""        # empty = alerting disabled
    notify_events: str = ""             # comma-separated event codes (see GET /notify/events)
    notify_min_interval_s: int = 300    # de-bounce per event+subject

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
    spool_lease_s: int = 300            # HA: how long a claim is held before takeover

    # High availability (several instances on one database) — see docs/ha.md
    instance_id: str = ""               # empty = hostname:pid (set it per instance)
    ha_heartbeat_s: int = 10            # how often this instance says "I am here"
    ha_instance_timeout_s: int = 60     # after this, an instance counts as gone

    # Circuit breaker per upstream source (C-FIND fan-out)
    breaker_fail_threshold: int = 3   # consecutive failures before opening
    breaker_open_seconds: int = 60    # how long an open breaker stays open

    # Local dev convenience: skip DICOM SCP + echo loop (tests)
    start_dicom: bool = True
    start_echo_loop: bool = True
    start_spool: bool = True
    start_atna: bool = True

    # Optional bootstrap: JSON list of sources/targets to upsert on startup
    seed_config_json: str = ""

    model_config = {"env_prefix": "BROKER_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
