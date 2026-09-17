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


def _setting(row: BrokerSetting) -> dict:
    return {"key": row.key, "value": row.value}


SERIALIZERS = {
    "source": (MwlSource, _source),
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
