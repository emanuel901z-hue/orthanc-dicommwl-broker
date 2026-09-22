"""Who is running? — the instance heartbeat behind high availability (B1).

Several broker instances may share one database and one spool volume (see
`docs/ha.md`). What they must not share is the *work*: an image is delivered
once (the spool claim, `spool.claim_items`) and the operator must be able to see
which instance is alive.

This module is deliberately small and has **no leader election**. The broker
keeps no state that needs a single owner — breaker, cache and spool live in the
database, and the DIMSE listeners are independent. The honest design is therefore
"both may work, nobody duplicates", plus visibility into who is there.

Each instance writes its own row every `ha_heartbeat_s`; an instance that has not
been seen for `ha_instance_timeout_s` counts as gone. Nothing here is patient
data: instance name, version, host, process id, timestamps.
"""
import logging
import os
import socket
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from .db import session_factory
from .models import BrokerInstance

log = logging.getLogger("mwl_broker.instances")

_lock = threading.Lock()
_cached_id: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def instance_id() -> str:
    """This process's name.

    `BROKER_INSTANCE_ID` (or the runtime setting) when set — that is what an
    operator should do in an HA deployment, because a hostname:pid is only
    unique until the container restarts.
    """
    global _cached_id
    with _lock:
        if _cached_id:
            return _cached_id
        from . import settings_service

        try:
            configured = settings_service.get_str("instance_id").strip()
        except Exception:  # DB not ready yet — fall back to something unique
            configured = ""
        _cached_id = configured or f"{socket.gethostname()}:{os.getpid()}"
        return _cached_id


def version() -> str:
    from . import __version__

    return __version__


def timeout_s() -> int:
    from . import settings_service

    return settings_service.get_int("ha_instance_timeout_s")


def heartbeat() -> None:
    """Say "I am here" — create the row on the first call, refresh it after.

    Upsert, because two instances starting at the same moment is the normal case
    in an HA deployment (and the row may already exist from an earlier run of the
    same name).
    """
    from . import db

    now = _now()
    with session_factory()() as s:
        db.upsert(
            s, BrokerInstance,
            values={"instance_id": instance_id(), "started_at": now, "last_seen": now,
                    "version": version(), "hostname": socket.gethostname(),
                    "pid": os.getpid()},
            index_elements=[BrokerInstance.instance_id],
            update_values={"last_seen": now, "version": version(),
                           "hostname": socket.gethostname(), "pid": os.getpid()},
        )
        s.commit()


def known(active_within_s: int | None = None) -> list[dict]:
    """Every known instance, newest activity first, with an `active` flag."""
    limit_s = timeout_s() if active_within_s is None else active_within_s
    now = _now()
    with session_factory()() as s:
        rows = s.scalars(
            select(BrokerInstance).order_by(BrokerInstance.last_seen.desc())
        ).all()
    out = []
    for row in rows:
        last_seen = row.last_seen
        if last_seen is not None and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        age = int((now - last_seen).total_seconds()) if last_seen else None
        out.append({
            "instance_id": row.instance_id,
            "started_at": row.started_at,
            "last_seen": row.last_seen,
            "age_s": age,
            "active": age is not None and age <= limit_s,
            "current": row.instance_id == instance_id(),
            "version": row.version,
            "hostname": row.hostname,
            "pid": row.pid,
        })
    return out


def active_count() -> int:
    return sum(1 for row in known() if row["active"])


def forget_stale(older_than_s: int = 86400) -> int:
    """Drop rows of instances that are long gone (a decommissioned host)."""
    cutoff = _now() - timedelta(seconds=older_than_s)
    with session_factory()() as s:
        removed = s.execute(
            delete(BrokerInstance).where(BrokerInstance.last_seen < cutoff)
        ).rowcount or 0
        s.commit()
    if removed:
        log.info("forgot %d broker instance(s) last seen before %s", removed, cutoff)
    return removed


def worker(stop: threading.Event, interval_s: int | None = None) -> None:
    """Background loop: write the heartbeat, forget long-gone instances."""
    ticks = 0
    while not stop.is_set():
        try:
            heartbeat()
            ticks += 1
            if ticks % 720 == 0:          # ~2 h at the default interval
                forget_stale()
        except Exception as exc:          # DB not ready yet — next tick retries
            log.warning("instance heartbeat failed: %s", exc)
        try:
            wait_s = interval_s or max(1, _interval())
        except Exception:
            wait_s = 10
        stop.wait(wait_s)


def _interval() -> int:
    from . import settings_service

    return settings_service.get_int("ha_heartbeat_s")


def reset_for_tests() -> None:
    global _cached_id
    with _lock:
        _cached_id = None
