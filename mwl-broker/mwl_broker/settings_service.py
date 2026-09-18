"""Runtime settings — DB override over the ENV default.

The deployment (.env) stays the source of truth for defaults; the UI may
override individual keys at runtime. `reset()` drops the override so the ENV
value applies again. Unknown keys are rejected (allowlist, not free-form).
"""
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .config import get_settings
from .db import get_session
from .models import BrokerSetting, SeenItem

log = logging.getLogger("mwl_broker.settings")

# key -> (kind, description). Keys mirror the ENV attribute names 1:1.
KNOWN: dict[str, tuple[str, str]] = {
    "allowed_calling_aets": (
        "aets",
        "Comma-separated calling AE titles allowed to query/store (empty = allow all).",
    ),
    "strict_store_status": (
        "bool",
        "Report a DIMSE failure to the modality when forwarding fails.",
    ),
    "seen_item_ttl_days": (
        "int",
        "Days that seen_items rows are kept for store routing (retention purge).",
    ),
    "echo_interval_s": (
        "int",
        "Interval of the C-ECHO monitoring loop in seconds.",
    ),
    "upstream_timeout_s": (
        "int",
        "Timeout for one upstream C-FIND query in seconds.",
    ),
    "audit_actor_header": (
        "str",
        "Header that carries the operator identity (empty = 'api').",
    ),
    "rbac_mode": (
        "enum:off,enforce",
        "enforce: configuration writes need the write role in the roles header.",
    ),
    "rbac_roles_header": (
        "str",
        "Header the proxy uses to pass the user's roles (comma separated).",
    ),
    "rbac_write_role": (
        "str",
        "Role that allows changing the configuration (brokerWrite).",
    ),
    "retention_query_log_days": (
        "int",
        "Keep worklist query logs for this many days (0 = forever).",
    ),
    "retention_store_log_days": (
        "int",
        "Retention of the forwarded-instance log in days (0 = keep forever).",
    ),
    "retention_local_items_days": (
        "int",
        "Also delete local worklist items older than this (0 = only their own validity applies).",
    ),
    "retention_hl7_days": (
        "int",
        "Keep inbound HL7 messages for this many days (0 = forever).",
    ),
    "retention_spool_days": (
        "int",
        "Keep spool entries (delivered and dead letters) for this many days (0 = forever).",
    ),
    "retention_config_audit_days": (
        "int",
        "Keep the configuration change log for this many days (0 = forever, recommended).",
    ),
    "tls_inbound_enabled": (
        "bool",
        "Offer a TLS listener for the modalities (next to the plain port).",
    ),
    "tls_inbound_port": (
        "int",
        "Port of the TLS listener (2762 is the usual DICOM TLS port).",
    ),
    "tls_inbound_cert_file": (
        "path",
        "Server certificate the modalities verify (PEM).",
    ),
    "tls_inbound_key_file": (
        "path",
        "Private key of the server certificate (PEM, unencrypted).",
    ),
    "tls_inbound_ca_file": (
        "path",
        "CA bundle used to verify modality certificates (for mTLS).",
    ),
    "tls_inbound_client_auth": (
        "enum:none,optional,required",
        "Whether modalities must present a certificate (mTLS).",
    ),
    "tls_outbound_ca_file": (
        "path",
        "CA bundle used to verify RIS/PACS certificates (empty = system store).",
    ),
    "tls_outbound_client_cert_file": (
        "path",
        "Certificate the broker presents to RIS/PACS (for mTLS).",
    ),
    "tls_outbound_client_key_file": (
        "path",
        "Private key of that certificate (PEM, unencrypted).",
    ),
    "tls_outbound_verify": (
        "bool",
        "Verify the remote certificate on outgoing connections.",
    ),
    "tls_dir": (
        "path",
        "Directory for certificates the broker generates itself.",
    ),
    "local_priority": (
        "int",
        "Merge priority of local worklist items (lower wins; default before every source).",
    ),
    "local_default_validity_days": (
        "int",
        "Default validity of a manually created local item in days (0 = unlimited).",
    ),
    "hl7_enabled": (
        "bool",
        "Accept HL7 ORM orders over the REST endpoint.",
    ),
    "hl7_mllp_enabled": (
        "bool",
        "Listen for HL7 ORM messages on the MLLP port as well.",
    ),
    "hl7_mllp_bind": (
        "str",
        "Interface the MLLP listener binds to.",
    ),
    "hl7_mllp_port": (
        "int",
        "MLLP port the RIS sends ORM messages to.",
    ),
    "hl7_default_station_aet": (
        "str",
        "Scheduled station used when an ORM message carries no station AE title.",
    ),
    "hl7_default_modality": (
        "str",
        "Modality used when an ORM message carries none.",
    ),
    "atna_enabled": (
        "bool",
        "Send IHE ATNA audit messages to an Audit Record Repository.",
    ),
    "atna_syslog_host": (
        "str",
        "Host of the audit repository (syslog/TLS receiver).",
    ),
    "atna_syslog_port": (
        "int",
        "Port of the audit repository (6514 = syslog over TLS, 514 = plain).",
    ),
    "atna_syslog_protocol": (
        "enum:tcp,tls",
        "Transport to the audit repository.",
    ),
    "atna_tls_ca_file": (
        "path",
        "Optional CA bundle used to verify the audit repository (TLS only).",
    ),
    "atna_queue_max": (
        "int",
        "Maximum buffered audit messages before the oldest are dropped.",
    ),
    "notify_webhook_url": (
        "url",
        "Webhook that receives broker alerts (Slack/Teams-compatible JSON, "
        "comma separated for several targets, empty = off).",
    ),
    "notify_events": (
        "events",
        "Comma-separated event codes to send (see GET /notify/events).",
    ),
    "notify_min_interval_s": (
        "int",
        "Minimum distance between two messages for the same event and object.",
    ),
    "spool_enabled": (
        "bool",
        "Spool C-STORE instances that cannot be forwarded and retry them later.",
    ),
    "accept_when_queued": (
        "bool",
        "Report success to the modality once the instance is safely spooled.",
    ),
    "spool_dir": (
        "path",
        "Directory the spooled DICOM files are written to (own volume recommended).",
    ),
    "spool_max_items": (
        "int",
        "Maximum number of spooled instances before the spool refuses new ones.",
    ),
    "spool_max_bytes": (
        "int",
        "Maximum spool size in bytes before it refuses new instances.",
    ),
    "spool_max_attempts": (
        "int",
        "Forwarding attempts before an instance becomes a dead letter.",
    ),
    "spool_backoff_s": (
        "int",
        "Base delay of the exponential retry backoff in seconds.",
    ),
    "spool_retention_s": (
        "int",
        "How long a forwarded entry stays as a duplicate guard (seconds).",
    ),
    "spool_poll_s": (
        "int",
        "Interval of the spool retry worker in seconds.",
    ),
    "cache_enabled": (
        "bool",
        "Serve cached worklist answers when an upstream source is unreachable.",
    ),
    "cache_stale_max_s": (
        "int",
        "Hard cap for serving cached answers after the last successful query (0 = never).",
    ),
    "cache_hide_completed": (
        "bool",
        "Never return COMPLETED/DISCONTINUED steps from the cache.",
    ),
    "cache_max_items": (
        "int",
        "Maximum number of worklist items cached per source.",
    ),
    "breaker_fail_threshold": (
        "int",
        "Consecutive C-FIND failures per source before its circuit breaker opens.",
    ),
    "breaker_open_seconds": (
        "int",
        "How long an open breaker stays open before the next attempt.",
    ),
}

_INT_RANGES: dict[str, tuple[int, int]] = {
    "seen_item_ttl_days": (1, 3650),
    "echo_interval_s": (5, 3600),
    "retention_query_log_days": (0, 36500),
    "retention_store_log_days": (0, 3650),
    "retention_local_items_days": (0, 3650),
    "retention_hl7_days": (0, 3650),
    "retention_spool_days": (0, 3650),
    "retention_config_audit_days": (0, 36500),
    "tls_inbound_port": (1, 65535),
    "local_priority": (-1000, 1000),
    "local_default_validity_days": (0, 3650),
    "hl7_mllp_port": (1, 65535),
    "atna_syslog_port": (1, 65535),
    "atna_queue_max": (100, 1000000),
    "notify_min_interval_s": (0, 86400),
    "spool_max_items": (1, 1000000),
    "spool_max_bytes": (1048576, 1099511627776),
    "spool_max_attempts": (1, 1000),
    "spool_backoff_s": (5, 86400),
    "spool_retention_s": (0, 2592000),
    "spool_poll_s": (1, 3600),
    "cache_stale_max_s": (0, 86400),
    "cache_max_items": (1, 100000),
    "breaker_fail_threshold": (1, 100),
    "breaker_open_seconds": (5, 3600),
}
_AET_RE = re.compile(r"^[A-Z0-9_-]{1,16}$")
_BOOL_TRUE = {"true", "1", "yes", "on"}


def _validate_url(value: str) -> list[str]:
    """A webhook URL must be http(s) — anything else is a configuration error."""
    if not value:
        return []  # empty = alerting disabled
    if not value.startswith(("http://", "https://")):
        return ["must start with http:// or https://"]
    return []


def _validate_events(value: str) -> list[str]:
    """Only known event codes may be subscribed."""
    from .notify import EVENTS

    codes = [part.strip() for part in (value or "").split(",") if part.strip()]
    unknown = [code for code in codes if code not in EVENTS]
    if unknown:
        return [f"unknown event(s): {', '.join(unknown)}"]
    return []


def _validate_path(value: str) -> list[str]:
    """A spool directory must be absolute and free of traversal."""
    if not value.startswith("/"):
        return ["must be an absolute path"]
    if ".." in value.split("/"):
        return ["must not contain '..'"]
    return []


def validate_value(key: str, raw: str) -> list[str]:
    """Return a list of validation errors (empty = valid)."""
    if key not in KNOWN:
        return [f"unknown setting {key!r}"]
    kind = KNOWN[key][0]
    raw = str(raw)
    if kind == "bool":
        if raw.strip().lower() not in _BOOL_TRUE | {"false", "0", "no", "off"}:
            return ["expected a boolean (true/false)"]
    elif kind == "int":
        try:
            n = int(raw)
        except ValueError:
            return ["expected an integer"]
        lo, hi = _INT_RANGES.get(key, (0, 10**9))
        if not lo <= n <= hi:
            return [f"must be between {lo} and {hi}"]
    elif kind.startswith("enum:"):
        choices = [c.strip() for c in kind.split(":", 1)[1].split(",") if c.strip()]
        if raw not in choices:
            return [f"must be one of: {', '.join(choices)}"]
    elif kind == "url":
        return _validate_url(raw)
    elif kind == "events":
        return _validate_events(raw)
    elif kind == "path":
        return _validate_path(raw)
    elif kind == "aets":
        bad = [p for p in (x.strip() for x in raw.split(",")) if p and not _AET_RE.match(p)]
        if bad:
            return [f"invalid AE title(s): {', '.join(bad)} (1-16 chars, A-Z 0-9 _ -)"]
    return []


def _env_default(key: str) -> str:
    return str(getattr(get_settings(), key))


def get_raw(key: str) -> tuple[str, str]:
    """Return (value, source) — source is 'db' or 'env'."""
    with get_session() as s:
        row = s.get(BrokerSetting, key)
    if row is not None:
        return row.value, "db"
    return _env_default(key), "env"


def get_str(key: str) -> str:
    return get_raw(key)[0]


def get_bool(key: str) -> bool:
    return get_str(key).strip().lower() in _BOOL_TRUE


def get_int(key: str) -> int:
    try:
        return int(get_str(key))
    except ValueError:
        return int(_env_default(key))


def get_aets(key: str = "allowed_calling_aets") -> list[str]:
    return [a.strip() for a in get_str(key).split(",") if a.strip()]


def _constraints(kind: str) -> dict:
    """Numeric bounds and enum choices so the UI can constrain its inputs."""
    if kind.startswith("enum:"):
        return {"choices": [c.strip() for c in kind.split(":", 1)[1].split(",") if c.strip()]}
    return {}


def list_all() -> list[dict]:
    with get_session() as s:
        rows = {r.key: r.value for r in s.scalars(select(BrokerSetting)).all()}
    out = []
    for key, (kind, description) in KNOWN.items():
        value = rows.get(key, _env_default(key))
        entry = {
            "key": key,
            "value": value,
            "default": _env_default(key),
            "source": "db" if key in rows else "env",
            "kind": kind,
            "description": description,
        }
        entry.update(_constraints(kind))
        if kind == "int":
            lo, hi = _INT_RANGES.get(key, (0, 10**9))
            entry["min"], entry["max"] = lo, hi
        out.append(entry)
    return out


def set_value(key: str, raw: str, session=None) -> None:
    """Upsert an override. Caller validates first (validate_value)."""
    def _write(s):
        row = s.get(BrokerSetting, key)
        if row is None:
            s.add(BrokerSetting(key=key, value=str(raw)))
        else:
            row.value = str(raw)
            row.updated_at = datetime.now(timezone.utc)
        s.commit()

    if session is not None:
        _write(session)
    else:
        with get_session() as s:
            _write(s)


def reset(key: str) -> None:
    """Drop the override — the ENV default applies again."""
    with get_session() as s:
        row = s.get(BrokerSetting, key)
        if row is not None:
            s.delete(row)
            s.commit()


def purge_seen_items(days: int | None = None) -> int:
    """Delete seen_items older than the retention window. Returns row count."""
    if days is None:
        days = get_int("seen_item_ttl_days")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_session() as s:
        rows = s.scalars(select(SeenItem).where(SeenItem.ts < cutoff)).all()
        for row in rows:
            s.delete(row)
        s.commit()
    if rows:
        log.info("retention: purged %d seen_items older than %d days", len(rows), days)
    return len(rows)
