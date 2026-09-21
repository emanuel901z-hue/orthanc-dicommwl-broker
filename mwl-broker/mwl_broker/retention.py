"""Retention and deletion — one place, one overview, one button.

Every table that stores operational data has a configurable retention window.
The operator sees per table how many rows there are, how old the oldest is and
what the configured retention is — and can run the cleanup from the UI instead
of waiting for the periodic tick. Nothing is deleted implicitly: a purge only
removes rows older than the configured window, and `0` days means "keep
forever".

The change log (`config_audit`) is included but defaults to "keep forever": it
is the accounting trail and is meant to outlive the operational data. The
worklist cache is **not** part of this module — it already has its own purge
(bounded by the stale window) and an explicit "clear cache" button.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from . import metrics, settings_service
from .db import session_factory
from .models import (
    MppsStep,ConfigAudit, Hl7Message, LocalWorklistItem, QueryLog,
                     SeenItem, StoreLog, StoreSpool)

log = logging.getLogger("mwl_broker.retention")

# table -> (retention setting, what the rows are, model, timestamp column)
TABLES: dict[str, tuple[str, str, type, str]] = {
    "query_log": ("retention_query_log_days", "Worklist queries (PHI-free log)",
                  QueryLog, "ts"),
    "store_log": ("retention_store_log_days", "Forwarded instances (metadata)",
                  StoreLog, "ts"),
    "seen_item": ("seen_item_ttl_days", "Worklist provenance for routing",
                  SeenItem, "ts"),
    "mpps_step": ("retention_mpps_days", "Performed procedure steps (MPPS)",
                  MppsStep, "ts"),
    "hl7_message": ("retention_hl7_days", "Inbound HL7 messages",
                    Hl7Message, "ts"),
    "local_worklist_item": ("retention_local_items_days",
                            "Local worklist items (PHI)",
                            LocalWorklistItem, "updated_at"),
    "store_spool": ("retention_spool_days", "Spool entries (delivered + dead)",
                    StoreSpool, "created_at"),
    "config_audit": ("retention_config_audit_days",
                     "Configuration change log (accounting)",
                     ConfigAudit, "ts"),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _cutoff(days: int) -> datetime:
    return _now() - timedelta(days=days)


def _setting_key(table: str) -> str:
    return TABLES[table][0]


def overview() -> dict:
    """Row counts, oldest row and the configured retention per table."""
    out = []
    with session_factory()() as s:
        for table, (setting_key, description, model, column_name) in TABLES.items():
            column = getattr(model, column_name)
            rows = int(s.scalar(select(func.count()).select_from(model)) or 0)
            oldest = _as_aware(s.scalar(select(func.min(column))))
            will_delete = 0
            days = settings_service.get_int(setting_key)
            if rows and days > 0:
                will_delete = int(s.scalar(
                    select(func.count()).select_from(model)
                    .where(column < _cutoff(days))
                ) or 0)
            out.append({
                "table": table,
                "description": description,
                "rows": rows,
                "oldest": oldest.isoformat() if oldest else None,
                "retention_days": days,
                "will_delete": will_delete,
            })
    return {"tables": out}


def purge(table: str | None = None) -> dict:
    """Delete everything older than the configured retention (one or all tables).

    `0` days means "keep forever" and is skipped — nothing is deleted implicitly.
    """
    removed: dict[str, int] = {}
    with session_factory()() as s:
        for name, (setting_key, _description, model, column_name) in TABLES.items():
            if table is not None and name != table:
                continue
            days = settings_service.get_int(setting_key)
            if days <= 0:
                removed[name] = 0
                continue
            result = s.execute(
                delete(model).where(getattr(model, column_name) < _cutoff(days))
            )
            removed[name] = result.rowcount or 0
        s.commit()
    total = sum(removed.values())
    if total:
        log.info("retention: purged %d row(s): %s", total,
                 {k: v for k, v in removed.items() if v})
    publish_metrics()
    return {"removed": removed, "total": total}


def publish_metrics() -> None:
    """Expose the age of the oldest row per table (a growing backlog is visible)."""
    for entry in overview()["tables"]:
        oldest = _as_aware(datetime.fromisoformat(entry["oldest"])) if entry["oldest"] else None
        age = int((_now() - oldest).total_seconds()) if oldest else 0
        metrics.RETENTION_OLDEST.labels(table=entry["table"]).set(age)


def reset_for_tests() -> None:
    """Nothing cached — kept so test fixtures stay uniform."""
