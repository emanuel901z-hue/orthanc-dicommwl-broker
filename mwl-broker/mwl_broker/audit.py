"""Server-side configuration change log.

Every mutation of the broker configuration is recorded with its before/after
snapshot. That is the basis for the change-log page, for the diff view and for
the rollback endpoint — and it is what an operator needs when a rule change
broke the routing at 3 a.m.

Configuration only: no patient data ever reaches this table.
"""
import logging

from sqlalchemy import select

from .config import get_settings
from .models import (
    BrokerSetting,
    LocalWorklistItem,
    StationRule,
    ConfigAudit,
    MwlSource,
    PacsTarget,
    RoutingRule,
    TransformRule,
)

log = logging.getLogger("mwl_broker.audit")

# entity name → (model, serializer)
def _source(row: MwlSource) -> dict:
    return {
        "name": row.name, "aet": row.aet, "host": row.host, "port": row.port,
        "calling_aet": row.calling_aet, "charset": row.charset,
        "enabled": row.enabled, "timeout_s": row.timeout_s, "priority": row.priority,
        "cache_stale_on_error": row.cache_stale_on_error,
        "cache_refresh_s": row.cache_refresh_s,
    }


def _target(row: PacsTarget) -> dict:
    return {
        "name": row.name, "aet": row.aet, "host": row.host, "port": row.port,
        "calling_aet": row.calling_aet, "enabled": row.enabled,
        "is_default": row.is_default,
    }


def _rule(row: RoutingRule) -> dict:
    return {
        "source_id": row.source_id, "target_id": row.target_id,
        "priority": row.priority, "enabled": row.enabled,
    }


def _transform(row: TransformRule) -> dict:
    return {
        "name": row.name, "enabled": row.enabled, "priority": row.priority,
        "source_id": row.source_id, "target_id": row.target_id,
        "operations": list(row.operations or []),
    }


def _local_item(row) -> dict:
    """Scheduling data only — deliberately without the patient identifiers.

    The change log (and the configuration export built from it) must stay
    PHI-free; the local worklist table itself is the place where the patient
    data lives. A rollback therefore restores the schedule, not the identity —
    the diff shows that, and the operator can complete the entry.
    """
    return {
        "accession": row.accession, "sps_id": row.sps_id,
        "modality": row.modality, "station_aet": row.station_aet,
        "procedure_description": row.procedure_description,
        "scheduled_date": row.scheduled_date, "scheduled_time": row.scheduled_time,
        "study_uid": row.study_uid, "sps_status": row.sps_status,
        "valid_until": row.valid_until.isoformat() if row.valid_until else None,
        "enabled": row.enabled, "origin": row.origin,
    }


def _station(row) -> dict:
    return {
        "name": row.name, "station_aet": row.station_aet, "mode": row.mode,
        "source_ids": list(row.source_ids or []),
        "source_priority": dict(row.source_priority or {}),
        "priority": row.priority, "enabled": row.enabled,
    }


def _setting(row: BrokerSetting) -> dict:
    return {"key": row.key, "value": row.value}


SERIALIZERS = {
    "source": (MwlSource, _source),
    "local_item": (LocalWorklistItem, _local_item),
    "station": (StationRule, _station),
    "target": (PacsTarget, _target),
    "rule": (RoutingRule, _rule),
    "transform": (TransformRule, _transform),
    "setting": (BrokerSetting, _setting),
}


def snapshot(entity: str, row) -> dict | None:
    """Serialized copy of a configuration row (None for a missing row).

    An unknown entity is a programming error and raises regardless of `row`.
    """
    serializer = SERIALIZERS.get(entity)
    if serializer is None:
        raise ValueError(f"unknown entity {entity!r}")
    return None if row is None else serializer[1](row)


def actor_from(headers) -> str:
    """Operator identity from the configured header (default 'api')."""
    header = get_settings().audit_actor_header
    if not header:
        return "api"
    value = headers.get(header)
    if not value:
        return "api"
    return str(value)[:128]


def record(session, actor: str, action: str, entity: str, entity_id: int | None,
           before: dict | None, after: dict | None, correlation_id: str = "") -> ConfigAudit:
    """Append a change-log entry. The caller owns the transaction."""
    entry = ConfigAudit(
        actor=actor or "api", action=action, entity=entity, entity_id=entity_id,
        before_json=before, after_json=after, correlation_id=correlation_id,
    )
    session.add(entry)
    log.info("config change: %s %s#%s by %s", action, entity, entity_id, entry.actor)
    return entry


def list_entries(session, entity: str | None = None, limit: int = 50,
                 offset: int = 0) -> list[ConfigAudit]:
    query = select(ConfigAudit).order_by(ConfigAudit.ts.desc(), ConfigAudit.id.desc())
    if entity:
        query = query.where(ConfigAudit.entity == entity)
    return session.scalars(query.limit(limit).offset(offset)).all()
