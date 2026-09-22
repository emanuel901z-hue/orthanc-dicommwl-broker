"""Per-source circuit breaker for the C-FIND fan-out.

A dead RIS must not cost every modality the full DIMSE timeout. After
`breaker_fail_threshold` consecutive failures a source is skipped for
`breaker_open_seconds`; the first query after that window probes it again
(half-open): success closes the breaker, failure re-opens it.

State is persisted in `source_breaker` so a broker restart remembers a
source is down. A missing row means "closed".
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import db, metrics, notify, settings_service
from .db import session_factory
from .models import MwlSource, SourceBreaker

log = logging.getLogger("mwl_broker.breaker")

STATE_CLOSED = "closed"
STATE_HALF_OPEN = "half_open"
STATE_OPEN = "open"

_STATE_GAUGE = {STATE_CLOSED: 0, STATE_HALF_OPEN: 1, STATE_OPEN: 2}

# Value recorded in the query log's per_source map when a source is skipped.
SKIPPED = "breaker_open"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _thresholds() -> tuple[int, int]:
    return (
        settings_service.get_int("breaker_fail_threshold"),
        settings_service.get_int("breaker_open_seconds"),
    )


def _as_aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes — treat them as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _publish(source_id: int, name: str, state: str) -> None:
    metrics.BREAKER_STATE.labels(source=name).set(_STATE_GAUGE.get(state, 0))


def is_available(source_id: int) -> bool:
    """Whether a source may be queried right now.

    An expired open window flips the breaker to half-open (one probe allowed)
    and returns True.
    """
    with session_factory()() as s:
        row = s.get(SourceBreaker, source_id)
        if row is None or row.state == STATE_CLOSED:
            return True
        if row.state == STATE_HALF_OPEN:
            return True
        open_until = _as_aware(row.open_until)
        if open_until is not None and _now() >= open_until:
            row.state = STATE_HALF_OPEN
            s.commit()
            log.info("breaker half-open (probing source %s)", source_id)
            return True
        return False


def record_success(source_id: int) -> None:
    """A source answered — close the breaker and reset the failure count."""
    with session_factory()() as s:
        row = s.get(SourceBreaker, source_id)
        if row is None:
            return
        was = row.state
        row.state = STATE_CLOSED
        row.failures = 0
        row.open_until = None
        row.last_error = ""
        s.commit()
    if was != STATE_CLOSED:
        log.info("breaker closed (source %s recovered)", source_id)
    _publish(source_id, _source_name(source_id), STATE_CLOSED)


def record_failure(source_id: int, error: str = "") -> None:
    """A source failed — open the breaker once the threshold is reached.

    The counter is incremented **by the database** (`failures = failures + 1`),
    not by reading and writing it back: at shift start many modalities query at
    once, and two of them failing on the same dead source must neither collide on
    the primary key (that raised out of the C-FIND handler and answered the
    modality with `0xC311`) nor lose an increment (the breaker would open later
    than configured).
    """
    threshold, open_seconds = _thresholds()
    now = _now()
    err = (error or "")[:512]

    with session_factory()() as s:
        db.upsert(
            s, SourceBreaker,
            values={"source_id": source_id, "state": STATE_CLOSED, "failures": 1,
                    "open_until": None, "last_error": err, "updated_at": now},
            index_elements=[SourceBreaker.source_id],
            update_values={"failures": SourceBreaker.failures + 1,
                           "last_error": err, "updated_at": now},
        )
        row = s.get(SourceBreaker, source_id)
        # A separate, idempotent decision instead of a CASE in the upsert: two
        # threads may both set OPEN, and setting the same value twice is fine.
        if row.failures >= threshold and row.state != STATE_OPEN:
            row.state = STATE_OPEN
            row.open_until = now + timedelta(seconds=open_seconds)
        s.commit()
        state = row.state
        failures = row.failures
    if state == STATE_OPEN:
        log.warning(
            "breaker open (source %s, %d consecutive failures, %ds cooldown)",
            source_id, failures, open_seconds,
        )
        name = _source_name(source_id)
        notify.notify("breaker_open",
                      f"Source '{name}' is skipped after {failures} consecutive failures.",
                      {"source": name, "failures": failures, "cooldown_s": open_seconds,
                       "error": (error or "")[:200]},
                      subject=name)
    _publish(source_id, _source_name(source_id), state)


def reset(source_id: int) -> None:
    """Force a source back into the fan-out (operator action)."""
    with session_factory()() as s:
        row = s.get(SourceBreaker, source_id)
        if row is not None:
            s.delete(row)
            s.commit()
    log.info("breaker reset by operator (source %s)", source_id)
    _publish(source_id, _source_name(source_id), STATE_CLOSED)


def forget(source_id: int) -> None:
    """Drop the state of a deleted source."""
    reset(source_id)


def state_of(source_id: int) -> str:
    """The breaker state of one source ("closed" when nothing was recorded)."""
    return (snapshot().get(source_id) or {}).get("state", STATE_CLOSED)


def snapshot() -> dict[int, dict]:
    """Breaker state per source id — used by /status and the health checks."""
    with session_factory()() as s:
        rows = s.scalars(select(SourceBreaker)).all()
        names = {r.id: r.name for r in s.scalars(select(MwlSource)).all()}
        now = _now()
        out: dict[int, dict] = {}
        for row in rows:
            open_until = _as_aware(row.open_until)
            retry_in = (
                max(0, int((open_until - now).total_seconds()))
                if row.state == STATE_OPEN and open_until is not None
                else None
            )
            out[row.source_id] = {
                "state": row.state,
                "failures": row.failures or 0,
                "retry_in_s": retry_in,
                "last_error": row.last_error or "",
                "name": names.get(row.source_id, ""),
            }
        return out


def _source_name(source_id: int) -> str:
    with session_factory()() as s:
        row = s.get(MwlSource, source_id)
        return row.name if row is not None else str(source_id)
