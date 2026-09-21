"""C-STORE spool — store and forward with retries and dead letters.

When a target PACS is unreachable the instance is **not** lost: the payload is
written to disk, the metadata goes into `store_spool`, and a worker retries with
an exponential backoff until it reaches the target (or becomes a dead letter
after `spool_max_attempts`).

Storage concept (see docs/roadmap-worklist-broker.md):

* The bytes live **on disk** (`spool_dir`, its own volume), the database keeps
  only metadata — a PACS outage must not bloat the index that serves the UI.
* A payload file exists while the entry is `queued`/`failed`/`dead`; after a
  successful send the file is deleted and only the row survives, as a duplicate
  guard for `spool_retention_s` (the same SOPInstanceUID is never sent twice).
* The spool has a hard budget (`spool_max_items`, `spool_max_bytes`). When it is
  exhausted the broker **refuses** the instance instead of silently dropping
  images — the modality sees a failure and retries, and the operator sees the
  finding in the health panel.
* `accept_when_queued` decides what the modality is told: with it (default) the
  broker acknowledges once the instance is safely persisted, which is the
  clinically correct answer — the images are not lost, they are queued.
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian
from pydicom.errors import InvalidDicomError
from pydicom.filereader import dcmread
from pydicom.filewriter import dcmwrite
from sqlalchemy import delete, func, select

from . import cstore, metrics, notify, settings_service
from .db import session_factory
from .models import StoreSpool

log = logging.getLogger("mwl_broker.spool")

STATUS_QUEUED = "queued"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_DEAD = "dead"

OPEN_STATUSES = (STATUS_QUEUED, STATUS_FAILED)
# Every status that occupies space in the spool budget.
HELD_STATUSES = (STATUS_QUEUED, STATUS_FAILED, STATUS_DEAD)


# ── settings ───────────────────────────────────────────────────────────


def enabled() -> bool:
    return settings_service.get_bool("spool_enabled")


def accept_when_queued() -> bool:
    return settings_service.get_bool("accept_when_queued")


def max_items() -> int:
    return settings_service.get_int("spool_max_items")


def max_bytes() -> int:
    return settings_service.get_int("spool_max_bytes")


def max_attempts() -> int:
    return settings_service.get_int("spool_max_attempts")


def backoff_s() -> int:
    return settings_service.get_int("spool_backoff_s")


def retention_s() -> int:
    return settings_service.get_int("spool_retention_s")


def poll_s() -> int:
    return settings_service.get_int("spool_poll_s")


def directory() -> Path:
    return Path(settings_service.get_str("spool_dir"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# ── payload files ──────────────────────────────────────────────────────


def _ensure_dir() -> Path:
    path = directory()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _payload_path(sop_uid: str) -> Path:
    # the SOP UID is a DICOM UID (digits and dots) — safe as a filename, but
    # sanitise defensively anyway
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in sop_uid)
    return directory() / f"{safe}.dcm"


def _ensure_file_meta(ds: Dataset) -> None:
    """Guarantee a writable file meta — an instance must never be lost here."""
    meta = getattr(ds, "file_meta", None)
    if meta is not None and "TransferSyntaxUID" in meta:
        return
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = ds.SOPClassUID
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta = meta


def _write_payload(ds: Dataset) -> tuple[str, int]:
    """Write the instance atomically and return (path, bytes)."""
    _ensure_dir()
    _ensure_file_meta(ds)
    target = _payload_path(str(ds.SOPInstanceUID))
    tmp = target.with_suffix(".tmp")
    dcmwrite(str(tmp), ds, write_like_original=False)
    with open(tmp, "rb") as handle:
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    return str(target), target.stat().st_size


def _read_payload(path: str) -> Dataset:
    try:
        return dcmread(path, force=True)
    except (InvalidDicomError, FileNotFoundError, OSError) as exc:
        raise FileNotFoundError(f"spooled payload unreadable: {path}") from exc


def _remove_payload(path: str) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError as exc:  # pragma: no cover - filesystem oddity
        log.warning("spool: cannot delete %s: %s", path, exc)


# ── capacity ───────────────────────────────────────────────────────────


def capacity(session=None) -> dict:
    """Current spool usage and whether it can still take instances."""
    own = session is None
    if own:
        session = session_factory()()
    try:
        # `execute()` — `scalars()` would only return the first column
        held = session.execute(
            select(func.count(StoreSpool.id), func.coalesce(func.sum(StoreSpool.payload_bytes), 0))
            .where(StoreSpool.status.in_(HELD_STATUSES))
        ).one()
        items, size = int(held[0] or 0), int(held[1] or 0)
    finally:
        if own:
            session.close()
    limit_items, limit_bytes = max_items(), max_bytes()
    return {
        "items": items,
        "bytes": size,
        "max_items": limit_items,
        "max_bytes": limit_bytes,
        "full": items >= limit_items or size >= limit_bytes,
    }


def _publish_capacity(cap: dict) -> None:
    metrics.SPOOL_BYTES.set(cap["bytes"])


# ── enqueue / retry / discard ──────────────────────────────────────────


def enqueue(ds: Dataset, source_id: int | None, target_id: int | None,
            target_name: str, error: str = "") -> str:
    """Spool an instance that could not be forwarded.

    Returns `queued`, `duplicate`, `full`, `disabled` or `error`.
    """
    if not enabled():
        return "disabled"
    sop_uid = str(getattr(ds, "SOPInstanceUID", "") or "")
    if not sop_uid:
        log.error("spool: instance without SOPInstanceUID — cannot spool it")
        return "error"

    with session_factory()() as s:
        existing = s.scalars(
            select(StoreSpool).where(StoreSpool.sop_instance_uid == sop_uid)
        ).first()
        if existing is not None and existing.status in (STATUS_QUEUED, STATUS_FAILED, STATUS_SENT):
            # already queued or already delivered — never send it twice
            log.info("spool: %s is already known (status %s)", sop_uid, existing.status)
            return "duplicate"

        cap = capacity(s)
        if cap["full"]:
            log.error(
                "spool is full (%d items / %d bytes) — refusing instance %s",
                cap["items"], cap["bytes"], sop_uid,
            )
            notify.notify("spool_full",
                          "The C-STORE spool is full — new instances are refused.",
                          {"items": cap["items"], "max_items": cap["max_items"],
                           "bytes": cap["bytes"], "max_bytes": cap["max_bytes"]},
                          subject="spool")
            return "full"

        try:
            path, size = _write_payload(ds)
        except Exception as exc:
            log.error("spool: cannot persist %s: %s", sop_uid, exc)
            return "error"

        if existing is not None:
            # a dead letter gets another chance instead of a second row
            existing.status = STATUS_QUEUED
            existing.attempts = 0
            existing.next_attempt_at = _now()
            existing.last_error = error[:512]
            existing.payload_path, existing.payload_bytes = path, size
            existing.target_id, existing.target_name = target_id, target_name
            row = existing
        else:
            row = StoreSpool(
                sop_instance_uid=sop_uid,
                study_uid=str(getattr(ds, "StudyInstanceUID", "") or ""),
                accession=str(getattr(ds, "AccessionNumber", "") or ""),
                source_id=source_id,
                target_id=target_id,
                target_name=target_name,
                payload_path=path,
                payload_bytes=size,
                status=STATUS_QUEUED,
                attempts=0,
                next_attempt_at=_now(),
                last_error=error[:512],
            )
            s.add(row)
        s.commit()
        metrics.SPOOL_QUEUED.labels(target=target_name or "none").inc()

    log.warning("spool: queued %s (%s) for retry — %s", sop_uid, target_name, error)
    _publish_capacity(capacity())
    return "queued"


def is_duplicate(sop_uid: str) -> bool:
    """Whether this instance is already spooled or delivered.

    Guards both paths: a queued entry must not be delivered twice (once by the
    worker, once by a live retry), and a delivered instance must not be stored
    again when the modality repeats the C-STORE.
    """
    if not sop_uid or not enabled():
        return False
    with session_factory()() as s:
        return s.scalars(
            select(StoreSpool.id)
            .where(StoreSpool.sop_instance_uid == sop_uid)
            .where(StoreSpool.status != STATUS_DEAD)
        ).first() is not None


def due_items(limit: int = 20) -> list[int]:
    """IDs of spooled instances that should be attempted now."""
    now = _now()
    with session_factory()() as s:
        rows = s.scalars(
            select(StoreSpool.id)
            .where(StoreSpool.status.in_(OPEN_STATUSES))
            .where((StoreSpool.next_attempt_at.is_(None)) | (StoreSpool.next_attempt_at <= now))
            .order_by(StoreSpool.created_at, StoreSpool.id)
            .limit(limit)
        ).all()
        return list(rows)


def _backoff(attempts: int) -> datetime:
    delay = min(backoff_s() * (2 ** max(0, attempts - 1)), 3600)
    return _now() + timedelta(seconds=delay)


def forward(item_id: int) -> str:
    """Try to forward one spooled instance. Returns the resulting status."""
    with session_factory()() as s:
        row = s.get(StoreSpool, item_id)
        if row is None:
            return "missing"
        target = cstore.resolve_target(s, row.target_id)
        if target is None:
            row.status = STATUS_DEAD
            row.last_error = "target is missing or disabled"
            s.commit()
            metrics.SPOOL_DEAD.labels(target=row.target_name or "none").inc()
            log.error("spool: %s → dead letter (target gone)", row.sop_instance_uid)
            notify.notify("spool_dead_letter",
                          f"Spooled instance for '{row.target_name}' gave up: target gone.",
                          {"sop_instance_uid": row.sop_instance_uid, "target": row.target_name,
                           "reason": "target is missing or disabled"},
                          subject=row.target_name or "none")
            return STATUS_DEAD
        try:
            ds = _read_payload(row.payload_path)
        except FileNotFoundError as exc:
            row.status = STATUS_DEAD
            row.last_error = str(exc)[:512]
            s.commit()
            metrics.SPOOL_DEAD.labels(target=target.name).inc()
            log.error("spool: %s → dead letter (%s)", row.sop_instance_uid, exc)
            notify.notify("spool_dead_letter",
                          f"Spooled instance for '{target.name}' gave up: {exc}",
                          {"sop_instance_uid": row.sop_instance_uid, "target": target.name,
                           "reason": str(exc)[:200]},
                          subject=target.name)
            return STATUS_DEAD

        try:
            cstore.send_store(ds, target)
        except Exception as exc:
            row.attempts += 1
            row.last_error = str(exc)[:512]
            if row.attempts >= max_attempts():
                row.status = STATUS_DEAD
                metrics.SPOOL_DEAD.labels(target=target.name).inc()
                log.error("spool: %s gave up after %d attempts — %s",
                          row.sop_instance_uid, row.attempts, exc)
                notify.notify("spool_dead_letter",
                              f"Spooled instance for '{target.name}' gave up after "
                              f"{row.attempts} attempts: {exc}",
                              {"sop_instance_uid": row.sop_instance_uid,
                               "target": target.name, "attempts": row.attempts,
                               "reason": str(exc)[:200]},
                              subject=target.name)
            else:
                row.status = STATUS_FAILED
                row.next_attempt_at = _backoff(row.attempts)
                log.warning("spool: retry %d for %s scheduled — %s",
                            row.attempts, row.sop_instance_uid, exc)
            s.commit()
            _publish_capacity(capacity(s))
            return row.status

        row.status = STATUS_SENT
        row.sent_at = _now()
        row.last_error = ""
        path = row.payload_path
        row.payload_path = ""
        row.payload_bytes = 0
        s.commit()
        metrics.SPOOL_FORWARDED.labels(target=target.name).inc()
        log.info("spool: %s delivered to %s", row.sop_instance_uid, target.name)

    # the payload is no longer needed — the row stays as a duplicate guard
    _remove_payload(path)
    _publish_capacity(capacity())
    return STATUS_SENT


def run_once(limit: int = 20) -> dict:
    """Process all instances that are due (used by the worker and by tests)."""
    if not enabled():
        return {"attempted": 0, "sent": 0, "failed": 0, "dead": 0, "disabled": 1}
    result = {"attempted": 0, "sent": 0, "failed": 0, "dead": 0}
    for item_id in due_items(limit):
        outcome = forward(item_id)
        result["attempted"] += 1
        if outcome == STATUS_SENT:
            result["sent"] += 1
        elif outcome == STATUS_DEAD:
            result["dead"] += 1
        elif outcome == STATUS_FAILED:
            result["failed"] += 1
    _publish_stats()
    return result


def worker(stop: threading.Event, interval_s: int | None = None) -> None:
    """Background loop: forward what is due, purge what is stale."""
    ticks = 0
    while not stop.is_set():
        try:
            run_once()
            _notify_backlog()
            ticks += 1
            if ticks % 60 == 0:
                purge()
        except Exception as exc:  # DB not ready yet — next tick retries
            log.warning("spool worker tick failed: %s", exc)
        try:
            wait_s = interval_s or poll_s()
        except Exception:
            wait_s = 10
        stop.wait(wait_s)


def _notify_backlog(threshold_s: int = 900) -> None:
    """Alert when instances wait too long (de-bounced by notify)."""
    data = stats()
    if not data["open"] or (data["oldest_age_s"] or 0) < threshold_s:
        return
    notify.notify("spool_backlog",
                  f"{data['open']} instance(s) are waiting in the spool "
                  f"(oldest {int((data['oldest_age_s'] or 0) / 60)} min).",
                  {"open": data["open"],
                   "oldest_minutes": int((data["oldest_age_s"] or 0) / 60)},
                  subject="spool")


def retry(item_id: int) -> bool:
    """Put one entry back into the queue immediately (operator action)."""
    with session_factory()() as s:
        row = s.get(StoreSpool, item_id)
        if row is None:
            return False
        if row.status == STATUS_SENT:
            return False
        row.status = STATUS_QUEUED
        row.next_attempt_at = _now()
        row.attempts = 0
        s.commit()
    log.info("spool: entry %s re-queued by the operator", item_id)
    return True


def retry_all() -> int:
    """Re-queue every failed/dead entry (after a PACS outage)."""
    with session_factory()() as s:
        rows = s.scalars(
            select(StoreSpool).where(StoreSpool.status.in_((STATUS_FAILED, STATUS_DEAD)))
        ).all()
        for row in rows:
            row.status = STATUS_QUEUED
            row.attempts = 0
            row.next_attempt_at = _now()
        s.commit()
        count = len(rows)
    if count:
        log.info("spool: %d entr(ies) re-queued by the operator", count)
    return count


def discard(item_id: int, reason: str) -> bool:
    """Drop one entry (payload + row). Requires an explicit reason."""
    with session_factory()() as s:
        row = s.get(StoreSpool, item_id)
        if row is None:
            return False
        path = row.payload_path
        s.delete(row)
        s.commit()
    _remove_payload(path)
    log.warning("spool: entry %s discarded (%s)", item_id, reason or "no reason given")
    _publish_capacity(capacity())
    return True


def purge() -> int:
    """Housekeeping: drop delivered entries once they are no longer a guard."""
    cutoff = _now() - timedelta(seconds=retention_s())
    with session_factory()() as s:
        result = s.execute(
            delete(StoreSpool)
            .where(StoreSpool.status == STATUS_SENT)
            .where(StoreSpool.sent_at.is_not(None))
            .where(StoreSpool.sent_at < cutoff)
        )
        s.commit()
        removed = result.rowcount or 0
    if removed:
        log.info("spool: purged %d delivered entr(ies)", removed)
        _publish_stats()
    return removed


# ── views ──────────────────────────────────────────────────────────────


def stats() -> dict:
    """Backlog overview for the dashboard and the health checks."""
    now = _now()
    with session_factory()() as s:
        rows = s.execute(
            select(StoreSpool.status, func.count(StoreSpool.id),
                   func.coalesce(func.sum(StoreSpool.payload_bytes), 0))
            .group_by(StoreSpool.status)
        ).all()
        counts = {status: int(count) for status, count, _size in rows}
        sizes = {status: int(size) for status, _count, size in rows}
        oldest = s.scalar(
            select(func.min(StoreSpool.created_at)).where(StoreSpool.status.in_(HELD_STATUSES))
        )
    oldest = _as_aware(oldest)
    cap = capacity()
    return {
        "queued": counts.get(STATUS_QUEUED, 0),
        "failed": counts.get(STATUS_FAILED, 0),
        "dead": counts.get(STATUS_DEAD, 0),
        "sent": counts.get(STATUS_SENT, 0),
        "open": counts.get(STATUS_QUEUED, 0) + counts.get(STATUS_FAILED, 0),
        "bytes": sum(sizes.get(status, 0) for status in HELD_STATUSES),
        "oldest_age_s": int((now - oldest).total_seconds()) if oldest is not None else None,
        "capacity": cap,
        "enabled": enabled(),
        "accept_when_queued": accept_when_queued(),
    }


def items(status: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """Spooled entries (metadata only — the payload stays on disk)."""
    now = _now()
    with session_factory()() as s:
        query = select(StoreSpool).order_by(StoreSpool.created_at.desc(), StoreSpool.id.desc())
        if status:
            query = query.where(StoreSpool.status == status)
        rows = s.scalars(query.offset(offset).limit(limit)).all()
        return [
            {
                "id": row.id,
                "sop_instance_uid": row.sop_instance_uid,
                "study_uid": row.study_uid,
                "accession": row.accession,
                "source_id": row.source_id,
                "target_id": row.target_id,
                "target_name": row.target_name,
                "status": row.status,
                "attempts": row.attempts,
                "last_error": row.last_error,
                "payload_bytes": row.payload_bytes,
                "age_s": int((now - _as_aware(row.created_at)).total_seconds()),
                "next_attempt_at": (
                    _as_aware(row.next_attempt_at).isoformat() if row.next_attempt_at else None
                ),
                "sent_at": _as_aware(row.sent_at).isoformat() if row.sent_at else None,
            }
            for row in rows
        ]


def _publish_stats() -> None:
    data = stats()
    for status in (STATUS_QUEUED, STATUS_FAILED, STATUS_DEAD, STATUS_SENT):
        metrics.SPOOL_ITEMS.labels(status=status).set(data[status])
    metrics.SPOOL_OLDEST.set(data["oldest_age_s"] or 0)
    metrics.SPOOL_BYTES.set(data["bytes"])


def reset_for_tests() -> None:
    """Remove spooled payloads from the configured directory (test isolation)."""
    try:
        for entry in directory().glob("*.dcm"):
            _remove_payload(str(entry))
    except FileNotFoundError:
        pass
