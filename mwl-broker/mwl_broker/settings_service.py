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
    "breaker_fail_threshold": (
        "int",
        "Consecutive C-FIND failures per source before its circuit breaker opens.",
    ),
    "breaker_open_seconds": (
        "int",
        "How long an open circuit breaker skips a source before probing it again.",
    ),
}

_INT_RANGES = {
    "seen_item_ttl_days": (1, 3650),
    "echo_interval_s": (5, 3600),
    "breaker_fail_threshold": (1, 100),
    "breaker_open_seconds": (5, 3600),
}
_AET_RE = re.compile(r"^[A-Z0-9_-]{1,16}$")
_BOOL_TRUE = {"true", "1", "yes", "on"}


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


def list_all() -> list[dict]:
    with get_session() as s:
        rows = {r.key: r.value for r in s.scalars(select(BrokerSetting)).all()}
    out = []
    for key, (kind, description) in KNOWN.items():
        value = rows.get(key, _env_default(key))
        out.append({
            "key": key,
            "value": value,
            "default": _env_default(key),
            "source": "db" if key in rows else "env",
            "kind": kind,
            "description": description,
        })
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
