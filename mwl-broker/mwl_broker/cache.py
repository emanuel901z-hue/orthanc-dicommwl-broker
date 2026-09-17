"""Worklist cache with a bounded stale fallback.

How other systems handle this (see docs/roadmap-worklist-broker.md):

- **Medavis RIS** keeps a worklist item available until the order is completed
  in the RIS — then it is simply no longer returned. Presence is the truth.
- **dcm4chee** drives the same lifecycle from HL7 ORM and DICOM MPPS and hides
  finished steps from the worklist (`dcmHideSPSWithStatusFromMWL: COMPLETED`);
  the SPS status `(0040,0020)` is the standard signal for "order closed".
- **Flux Capacitor** (worklist proxy) caches snapshots per query, compares each
  refresh against the previous snapshot and can serve stale results for a
  configurable window (`ServeStaleForSeconds`) before the query goes
  "degraded".

The broker follows that model instead of a "keep it for N minutes" TTL:

1. The upstream is the source of truth. A successful query **replaces** the
   whole snapshot for that source, so completed/cancelled orders disappear
   immediately — nothing is kept alive locally.
2. The cache is served **only** when the upstream fails, and only within
   `cache_stale_max_s` (default 120 s). `0` disables stale serving entirely.
3. Stale answers never resurrect a finished step: items with SPS status
   COMPLETED/DISCONTINUED are filtered out of cached answers
   (`cache_hide_completed`).
4. Snapshots are bounded (`cache_max_items`) and purged automatically.

`payload` contains PHI (that is what a worklist is). It is never logged and
never exposed through the API — the cache endpoints return metadata only.
"""
import logging
from datetime import datetime, timedelta, timezone

from pydicom.dataset import Dataset
from sqlalchemy import delete, func, select

from . import metrics, settings_service
from .db import session_factory
from .models import MwlSource, WorklistCache
from .upstream import dedupe_key

log = logging.getLogger("mwl_broker.cache")

# SPS status values that mean "this step is done" — never serve them from cache.
FINISHED_STATUS = {"COMPLETED", "DISCONTINUED"}
# Value used for items whose status could not be read (unknown RIS behaviour).
UNKNOWN_STATUS = ""

STATE_EMPTY = "empty"
STATE_EXPIRED = "expired"
STATE_AVAILABLE = "available"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _first_sps(ds: Dataset) -> Dataset | None:
    seq = ds.get("ScheduledProcedureStepSequence") or []
    return seq[0] if seq else None


def _describe(ds: Dataset) -> dict:
    """Non-PHI metadata for the cache index (accession is allowed by policy)."""
    sps = _first_sps(ds)
    status = ""
    station = ""
    if sps is not None:
        status = str(sps.get("ScheduledProcedureStepStatus", "") or "").strip().upper()
        station = str(sps.get("ScheduledStationAETitle", "") or "").strip()
    return {
        "accession": str(ds.get("AccessionNumber", "") or "").strip(),
        "study_uid": str(ds.get("StudyInstanceUID", "") or "").strip(),
        "modality": str((sps.get("Modality", "") if sps is not None else "") or "").strip(),
        "station_aet": station,
        "sps_status": status,
    }


def is_enabled() -> bool:
    return settings_service.get_bool("cache_enabled")


def stale_max_s() -> int:
    return settings_service.get_int("cache_stale_max_s")


def max_items() -> int:
    return settings_service.get_int("cache_max_items")


def hide_completed() -> bool:
    return settings_service.get_bool("cache_hide_completed")


def stale_allowed(source_id: int) -> bool:
    """Global switch + per-source opt-out."""
    if not is_enabled() or stale_max_s() <= 0:
        return False
    with session_factory()() as s:
        row = s.get(MwlSource, source_id)
        return bool(row is not None and row.cache_stale_on_error)


def store_snapshot(source_id: int, answers: list[Dataset]) -> int:
    """Replace the cached snapshot of one source with the upstream answer.

    Items that are no longer in the answer (completed/cancelled orders) are
    dropped — the RIS is the source of truth.
    """
    if not is_enabled():
        return 0
    limit = max_items()
    if len(answers) > limit:
        log.warning(
            "cache: source %s returned %d items — caching the first %d",
            source_id, len(answers), limit,
        )
        answers = answers[:limit]

    now = _now()
    seen: set[str] = set()
    stored = 0
    with session_factory()() as s:
        existing = {
            row.dedupe_key: row
            for row in s.scalars(
                select(WorklistCache).where(WorklistCache.source_id == source_id)
            ).all()
        }
        for ds in answers:
            key = "|".join(dedupe_key(ds))
            seen.add(key)
            meta = _describe(ds)
            row = existing.get(key)
            if row is None:
                row = WorklistCache(source_id=source_id, dedupe_key=key)
                s.add(row)
            row.accession = meta["accession"]
            row.study_uid = meta["study_uid"]
            row.modality = meta["modality"]
            row.station_aet = meta["station_aet"]
            row.sps_status = meta["sps_status"]
            row.payload = {"json": ds.to_json()}
            row.fetched_at = now
            stored += 1

        gone = [row for key, row in existing.items() if key not in seen]
        for row in gone:
            s.delete(row)
        s.commit()

    if gone:
        metrics.CACHE_DROPPED.labels(source=source_id, reason="gone_from_upstream").inc(len(gone))
        log.info("cache: %d item(s) dropped for source %s (no longer in the worklist)",
                 len(gone), source_id)
    metrics.CACHE_ENTRIES.labels(source=source_id).set(stored)
    metrics.CACHE_REFRESH.labels(source=source_id, result="ok").inc()
    return stored


def stale_answers(source_id: int) -> tuple[list[Dataset], int | None]:
    """Cached answers for a source that just failed.

    Returns `([], None)` when stale serving is disabled, the cache is empty, it
    is older than the allowed window, or nothing usable is left in it (all
    steps finished / unreadable payload). Otherwise the answers plus their age.
    """
    if not stale_allowed(source_id):
        metrics.CACHE_REFRESH.labels(source=source_id, result="disabled").inc()
        return [], None

    with session_factory()() as s:
        rows = s.scalars(
            select(WorklistCache)
            .where(WorklistCache.source_id == source_id)
            .order_by(WorklistCache.id)
        ).all()
        if not rows:
            metrics.CACHE_REFRESH.labels(source=source_id, result="empty").inc()
            return [], None
        newest = max(_as_aware(r.fetched_at) for r in rows)
        age = int((_now() - newest).total_seconds())
        if age > stale_max_s():
            metrics.CACHE_REFRESH.labels(source=source_id, result="expired").inc()
            log.warning("cache: snapshot for source %s is %ds old — not serving it",
                        source_id, age)
            return [], None
        payloads = [((r.payload or {}).get("json", ""), r.sps_status) for r in rows]

    answers: list[Dataset] = []
    skipped = 0
    for raw, status in payloads:
        if not raw:
            continue
        if hide_completed() and (status or UNKNOWN_STATUS) in FINISHED_STATUS:
            skipped += 1
            continue
        try:
            answers.append(Dataset.from_json(raw))
        except Exception as exc:  # corrupt payload — never break the query
            log.warning("cache: unreadable payload for source %s: %s", source_id, exc)
    if skipped:
        metrics.CACHE_DROPPED.labels(source=source_id, reason="completed").inc(skipped)
    if not answers:
        # nothing servable (all steps finished, or the payloads are unreadable)
        metrics.CACHE_REFRESH.labels(source=source_id, result="nothing_to_serve").inc()
        return [], None

    metrics.CACHE_SERVED.labels(source=source_id).inc()
    metrics.CACHE_AGE.labels(source=source_id).set(age)
    log.warning("cache: serving %d item(s) for source %s from a %ds old snapshot",
                len(answers), source_id, age)
    return answers, age


def stats() -> list[dict]:
    """Cache state per source (metadata only — no PHI)."""
    now = _now()
    window = stale_max_s()
    with session_factory()() as s:
        sources = s.scalars(select(MwlSource).order_by(MwlSource.priority, MwlSource.id)).all()
        grouped = {
            row[0]: (row[1], row[2])
            for row in s.execute(
                select(
                    WorklistCache.source_id,
                    func.count(WorklistCache.id),
                    func.max(WorklistCache.fetched_at),
                ).group_by(WorklistCache.source_id)
            ).all()
        }
        out = []
        for source in sources:
            count, newest = grouped.get(source.id, (0, None))
            newest = _as_aware(newest)
            age = int((now - newest).total_seconds()) if newest is not None else None
            if not count:
                state = STATE_EMPTY
            elif window <= 0 or (age is not None and age > window):
                state = STATE_EXPIRED
            else:
                state = STATE_AVAILABLE
            out.append({
                "source_id": source.id,
                "source_name": source.name,
                "entries": count,
                "age_s": age,
                "state": state,
                "stale_on_error": bool(source.cache_stale_on_error),
                "refresh_s": source.cache_refresh_s,
                "newest_fetched_at": newest.isoformat() if newest else None,
            })
        return out


def items(source_id: int | None = None, limit: int = 100) -> list[dict]:
    """Cached items as metadata (deliberately without patient identifiers)."""
    with session_factory()() as s:
        query = select(WorklistCache, MwlSource.name).join(
            MwlSource, MwlSource.id == WorklistCache.source_id
        ).order_by(WorklistCache.fetched_at.desc(), WorklistCache.id)
        if source_id is not None:
            query = query.where(WorklistCache.source_id == source_id)
        rows = s.execute(query.limit(limit)).all()
        now = _now()
        return [
            {
                "source_id": row.source_id,
                "source_name": name,
                "accession": row.accession,
                "study_uid": row.study_uid,
                "modality": row.modality,
                "station_aet": row.station_aet,
                "sps_status": row.sps_status,
                "age_s": int((now - _as_aware(row.fetched_at)).total_seconds()),
                "fetched_at": _as_aware(row.fetched_at).isoformat(),
            }
            for row, name in rows
        ]


def clear(source_id: int | None = None) -> int:
    """Delete the cache (one source or everything) — the operator's kill switch."""
    with session_factory()() as s:
        query = delete(WorklistCache)
        if source_id is not None:
            query = query.where(WorklistCache.source_id == source_id)
        result = s.execute(query)
        s.commit()
        removed = result.rowcount or 0
    if source_id is not None:
        metrics.CACHE_ENTRIES.labels(source=source_id).set(0)
    log.info("cache: cleared %d item(s) (%s)", removed,
             f"source {source_id}" if source_id is not None else "all sources")
    return removed


def purge() -> int:
    """Housekeeping: drop snapshots that can never be served again."""
    keep = max(stale_max_s(), 1) * 2
    cutoff = _now() - timedelta(seconds=keep)
    with session_factory()() as s:
        result = s.execute(delete(WorklistCache).where(WorklistCache.fetched_at < cutoff))
        s.commit()
        removed = result.rowcount or 0
    if removed:
        log.info("cache: purged %d expired item(s) (older than %ds)", removed, keep)
        for entry in stats():
            metrics.CACHE_ENTRIES.labels(source=entry["source_id"]).set(entry["entries"])
    return removed


def refresh(source) -> int:
    """Background refresh for one source (used by the echo loop)."""
    from .upstream import query_source

    try:
        answers = query_source(source, Dataset())
    except Exception as exc:
        metrics.CACHE_REFRESH.labels(source=source.id, result="error").inc()
        log.warning("cache: background refresh of %s failed: %s", source.name, exc)
        return 0
    stored = store_snapshot(source.id, answers)
    log.info("cache: background refresh of %s stored %d item(s)", source.name, stored)
    return stored


def sources_due_for_refresh() -> list:
    """Enabled sources whose snapshot should be refreshed now."""
    now = _now()
    out = []
    with session_factory()() as s:
        rows = s.scalars(
            select(MwlSource)
            .where(MwlSource.enabled.is_(True), MwlSource.cache_refresh_s > 0)
            .order_by(MwlSource.priority, MwlSource.id)
        ).all()
        for row in rows:
            newest = s.scalar(
                select(func.max(WorklistCache.fetched_at)).where(
                    WorklistCache.source_id == row.id
                )
            )
            newest = _as_aware(newest)
            if newest is None or (now - newest).total_seconds() >= row.cache_refresh_s:
                out.append(row)
    # detached copies are enough for the query helper
    from .upstream import SourceCfg

    return [
        SourceCfg(id=r.id, name=r.name, aet=r.aet, host=r.host, port=r.port,
                  calling_aet=r.calling_aet, charset=r.charset, timeout_s=r.timeout_s,
                  priority=r.priority)
        for r in out
    ]
