"""Per-station worklist filtering and source priority.

A modality queries with a `ScheduledStationAETitle`; the matching station rule
decides which sources are visible for that console and in which order they win
the dedupe. The filter runs **after** the merge on purpose: deduplication must
not depend on station rules (the same accession has to collapse to one item
regardless of who asks).
"""
import logging

from pydicom.dataset import Dataset
from sqlalchemy import select

from .db import session_factory
from .models import StationRule

log = logging.getLogger("mwl_broker.station_rules")

FALLBACK_STATION = "*"


def query_station(identifier: Dataset) -> str:
    """The `ScheduledStationAETitle` of an incoming C-FIND ('' when absent)."""
    sps_seq = identifier.get("ScheduledProcedureStepSequence") or []
    if sps_seq:
        value = str(sps_seq[0].get("ScheduledStationAETitle", "") or "").strip()
        if value:
            return value.upper()
    return str(identifier.get("ScheduledStationAETitle", "") or "").strip().upper()


def _snapshot(row: StationRule) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "station_aet": row.station_aet,
        "mode": row.mode,
        "source_ids": list(row.source_ids or []),
        "source_priority": dict(row.source_priority or {}),
        "priority": row.priority,
        "enabled": row.enabled,
    }


def matching_rule(station_aet: str) -> dict | None:
    """The first enabled rule for this station (exact match before the fallback)."""
    station = (station_aet or "").strip().upper()
    with session_factory()() as s:
        rows = s.scalars(
            select(StationRule)
            .where(StationRule.enabled.is_(True))
            .order_by(StationRule.priority, StationRule.id)
        ).all()
        candidates = [row for row in rows if row.station_aet.upper() == station]
        if not candidates and station:
            candidates = [row for row in rows if row.station_aet == FALLBACK_STATION]
        return _snapshot(candidates[0]) if candidates else None


def source_visible(rule: dict | None, source_id: int) -> bool:
    """Whether a source's answers are shown to the station."""
    if rule is None:
        return True
    listed = {int(sid) for sid in rule["source_ids"]}
    if rule["mode"] == "allow":
        return source_id in listed
    return source_id not in listed


def order_sources(sources: list, rule: dict | None) -> list:
    """Apply the station's priority override to the fan-out order."""
    if rule is None or not rule["source_priority"]:
        return sources
    overrides = {int(k): int(v) for k, v in rule["source_priority"].items()}
    return sorted(sources, key=lambda src: (overrides.get(src.id, src.priority), src.id))


def filter_merged(merged: list[tuple[Dataset, object]], rule: dict | None) -> tuple[list, int]:
    """Drop answers of hidden sources (called after the merge)."""
    if rule is None:
        return merged, 0
    kept = [(ds, src) for ds, src in merged if source_visible(rule, src.id)]
    return kept, len(merged) - len(kept)


def preview(station_aet: str, sources: list) -> dict:
    """What a station would see — used by the simulation endpoint and the UI."""
    rule = matching_rule(station_aet)
    ordered = order_sources(sources, rule)
    overrides = {int(k): int(v) for k, v in (rule or {}).get("source_priority", {}).items()}
    return {
        "station_aet": (station_aet or "").strip().upper(),
        "rule_id": (rule or {}).get("id"),
        "rule_name": (rule or {}).get("name"),
        "mode": (rule or {}).get("mode"),
        "sources": [
            {
                "id": src.id,
                "name": src.name,
                "visible": source_visible(rule, src.id),
                "effective_priority": overrides.get(src.id, src.priority),
            }
            for src in ordered
        ],
        "reason": (
            f"station rule '{rule['name']}' ({rule['mode']} {rule['source_ids']})"
            if rule else "no station rule — every source is visible"
        ),
    }


def reset_for_tests() -> None:  # symmetry with the other modules
    """Nothing cached in this module — kept so test fixtures stay uniform."""
