"""Reporting: how busy is the broker, and where does it hurt?

Everything here is derived from the logs the broker already writes (query log,
store log, MPPS steps, spool) — no extra bookkeeping, no PHI. The numbers an
operator and a quality manager ask for:

* how many worklist queries per station, and how many answers they produced,
* how many images were forwarded, and how many failed,
* which source contributed how much, and how often it was unreachable,
* how the volume developed over the days of the period.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .db import session_factory
from .models import MppsStep, QueryLog, StoreLog, StoreSpool, MwlSource

log = logging.getLogger("mwl_broker.stats")

DEFAULT_DAYS = 7
MAX_DAYS = 366


def _window(days: int) -> tuple[datetime, datetime]:
    days = max(1, min(days, MAX_DAYS))
    now = datetime.now(timezone.utc)
    return now - timedelta(days=days), now


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def overview(days: int = DEFAULT_DAYS, group_by: str = "source") -> dict:
    """Totals, per-group breakdown and a daily series for the period."""
    start, end = _window(days)
    with session_factory()() as s:
        queries = s.scalars(select(QueryLog).where(QueryLog.ts >= start)).all()
        stores = s.scalars(select(StoreLog).where(StoreLog.ts >= start)).all()
        mpps_rows = s.scalars(select(MppsStep).where(MppsStep.ts >= start)).all()
        spool_rows = s.scalars(select(StoreSpool)).all()
        source_names = {row.id: row.name for row in s.scalars(select(MwlSource)).all()}

    durations = [q.duration_ms for q in queries if q.duration_ms]
    answers = sum(q.answers or 0 for q in queries)
    stale = sum(1 for q in queries if (q.served_stale or []))
    failed_queries = sum(1 for q in queries if q.status == "failed")
    forwarded = sum(1 for st in stores if st.status == "success")
    failed_stores = sum(1 for st in stores if st.status == "failed")
    unrouted = sum(1 for st in stores if st.status == "unrouted")
    completed = sum(1 for m in mpps_rows if m.status != "IN PROGRESS")
    pending_forward = sum(1 for m in mpps_rows if not m.forwarded and m.status != "IN PROGRESS")

    totals = {
        "days": days,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "queries": len(queries),
        "answers": answers,
        "queries_failed": failed_queries,
        "queries_from_cache": stale,
        "avg_duration_ms": int(sum(durations) / len(durations)) if durations else 0,
        "stores": len(stores),
        "stores_forwarded": forwarded,
        "stores_failed": failed_stores,
        "stores_unrouted": unrouted,
        "mpps_steps": len(mpps_rows),
        "mpps_completed": completed,
        "mpps_pending_forward": pending_forward,
        "spool_open": sum(1 for r in spool_rows if r.status in ("queued", "failed")),
        "spool_dead": sum(1 for r in spool_rows if r.status == "dead"),
    }

    # ── per group ──────────────────────────────────────────────────────────
    groups: dict[str, dict] = {}

    def bucket(name: str) -> dict:
        return groups.setdefault(name or "(unbekannt)", {
            "name": name or "(unbekannt)", "queries": 0, "answers": 0,
            "queries_failed": 0, "stores": 0, "stores_failed": 0,
        })

    if group_by == "station":
        for q in queries:
            key = str((q.query_keys or {}).get("SPS", {}).get("ScheduledStationAETitle", "")) \
                if isinstance(q.query_keys, dict) else ""
            entry = bucket(key)
            entry["queries"] += 1
            entry["answers"] += q.answers or 0
            if q.status == "failed":
                entry["queries_failed"] += 1
    elif group_by == "modality":
        for q in queries:
            key = str((q.query_keys or {}).get("Modality", "")) if isinstance(q.query_keys, dict) else ""
            entry = bucket(key)
            entry["queries"] += 1
            entry["answers"] += q.answers or 0
            if q.status == "failed":
                entry["queries_failed"] += 1
    else:  # source
        for q in queries:
            per = q.per_source or {}
            for name, count in per.items():
                entry = bucket(str(name))
                if isinstance(count, int):
                    entry["answers"] += count
                else:
                    entry["queries_failed"] += 1
            for name in per:
                bucket(str(name))["queries"] += 1
        for st in stores:
            name = source_names.get(st.source_id or -1, "")
            if name:
                entry = bucket(name)
                entry["stores"] += 1
                if st.status == "failed":
                    entry["stores_failed"] += 1

    # ── daily series ───────────────────────────────────────────────────────
    series: dict[str, dict] = {}
    day = start.date()
    while day <= end.date():
        series[day.isoformat()] = {"day": day.isoformat(), "queries": 0, "stores": 0, "mpps": 0}
        day += timedelta(days=1)

    def day_of(ts: datetime | None) -> str | None:
        ts = _aware(ts)
        return ts.date().isoformat() if ts else None

    for q in queries:
        key = day_of(q.ts)
        if key in series:
            series[key]["queries"] += 1
    for st in stores:
        key = day_of(st.ts)
        if key in series:
            series[key]["stores"] += 1
    for m in mpps_rows:
        key = day_of(m.ts)
        if key in series:
            series[key]["mpps"] += 1

    return {
        "totals": totals,
        "groups": sorted(groups.values(), key=lambda g: (-g["queries"], -g["stores"], g["name"])),
        "series": [series[key] for key in sorted(series)],
        "group_by": group_by,
    }
