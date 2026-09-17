"""Configuration export / import (dry-run diff + apply) and rollback.

The export is portable: rules and modify rules reference sources/targets by
**name**, so a staging export can be imported into production without id
mapping. Import is upsert-only — nothing is ever deleted implicitly, because a
missing entry in a file is not a statement about production.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from . import audit, settings_service
from .models import BrokerSetting, MwlSource, PacsTarget, RoutingRule, TransformRule

log = logging.getLogger("mwl_broker.config_io")

SCHEMA_VERSION = 1

# Fields that identify an entry and are therefore not part of the diff.
_IDENTITY = {"name", "key", "source", "target"}


def export_config(session) -> dict:
    """Full configuration as a portable JSON document."""
    sources = session.scalars(select(MwlSource).order_by(MwlSource.id)).all()
    targets = session.scalars(select(PacsTarget).order_by(PacsTarget.id)).all()
    rules = session.scalars(select(RoutingRule).order_by(RoutingRule.id)).all()
    transforms = session.scalars(select(TransformRule).order_by(TransformRule.id)).all()
    settings = session.scalars(select(BrokerSetting)).all()

    src_names = {s.id: s.name for s in sources}
    tgt_names = {t.id: t.name for t in targets}

    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "sources": [audit.snapshot("source", s) for s in sources],
        "targets": [audit.snapshot("target", t) for t in targets],
        "rules": [
            {
                "source": src_names.get(r.source_id, ""),
                "target": tgt_names.get(r.target_id, ""),
                "priority": r.priority,
                "enabled": r.enabled,
            }
            for r in rules
        ],
        "transforms": [
            {
                **audit.snapshot("transform", t),
                "source": src_names.get(t.source_id, "") or None,
                "target": tgt_names.get(t.target_id, "") or None,
            }
            for t in transforms
        ],
        "settings": {s.key: s.value for s in settings},
    }


def _normalize_operations(operations) -> list[dict]:
    """Drop unset optional fields — same shape the transform endpoints store.

    Without this a re-import would not be idempotent (Pydantic dumps explicit
    `None`s, the live API strips them).
    """
    return [
        {key: value for key, value in op.items() if value is not None}
        for op in (operations or [])
    ]


def _diff_fields(before: dict, after: dict) -> dict:
    """Field-level differences (after-values), identity fields excluded."""
    out = {}
    for key, value in after.items():
        if key in _IDENTITY:
            continue
        if before.get(key) != value:
            out[key] = value
    return out


def _rows_by_name(session, model) -> dict[str, object]:
    return {row.name: row for row in session.scalars(select(model)).all()}


def plan_import(session, payload: dict) -> dict:
    """Compute what an import would change — no writes."""
    changes: list[dict] = []
    skipped: list[str] = []

    sources = _rows_by_name(session, MwlSource)
    targets = _rows_by_name(session, PacsTarget)
    transforms = _rows_by_name(session, TransformRule)
    settings = {s.key: s for s in session.scalars(select(BrokerSetting)).all()}

    # A document may create the very nodes its rules reference — so the plan
    # resolves names against the database *plus* the document itself.
    source_names = set(sources) | {item["name"] for item in payload.get("sources", [])}
    target_names = set(targets) | {item["name"] for item in payload.get("targets", [])}

    for item in payload.get("sources", []):
        existing = sources.get(item["name"])
        if existing is None:
            changes.append({"entity": "source", "action": "create", "name": item["name"],
                            "fields": _diff_fields({}, item)})
        else:
            fields = _diff_fields(audit.snapshot("source", existing), item)
            if fields:
                changes.append({"entity": "source", "action": "update", "name": item["name"],
                                "fields": fields})

    for item in payload.get("targets", []):
        existing = targets.get(item["name"])
        if existing is None:
            changes.append({"entity": "target", "action": "create", "name": item["name"],
                            "fields": _diff_fields({}, item)})
        else:
            fields = _diff_fields(audit.snapshot("target", existing), item)
            if fields:
                changes.append({"entity": "target", "action": "update", "name": item["name"],
                                "fields": fields})

    for item in payload.get("rules", []):
        if item["source"] not in source_names or item["target"] not in target_names:
            skipped.append(f"rule {item['source']} → {item['target']}: unknown source or target")
            continue
        src, tgt = sources.get(item["source"]), targets.get(item["target"])
        existing = None
        if src is not None and tgt is not None:
            existing = session.scalars(
                select(RoutingRule).where(
                    RoutingRule.source_id == src.id, RoutingRule.target_id == tgt.id
                )
            ).first()
        fields = {"priority": item.get("priority", 100), "enabled": item.get("enabled", True)}
        if existing is None:
            changes.append({"entity": "rule", "action": "create",
                            "name": f"{item['source']} → {item['target']}", "fields": fields})
        else:
            diff = _diff_fields(audit.snapshot("rule", existing), fields)
            if diff:
                changes.append({"entity": "rule", "action": "update",
                                "name": f"{item['source']} → {item['target']}", "fields": diff})

    for item in payload.get("transforms", []):
        scope_source = item.get("source") or None
        scope_target = item.get("target") or None
        if scope_source and scope_source not in source_names:
            skipped.append(f"modify rule {item['name']}: unknown source {scope_source}")
            continue
        if scope_target and scope_target not in target_names:
            skipped.append(f"modify rule {item['name']}: unknown target {scope_target}")
            continue
        fields = {
            "enabled": item.get("enabled", True),
            "priority": item.get("priority", 100),
            "operations": _normalize_operations(item.get("operations", [])),
        }
        existing = transforms.get(item["name"])
        if existing is None:
            changes.append({"entity": "transform", "action": "create", "name": item["name"],
                            "fields": fields})
        else:
            diff = _diff_fields(audit.snapshot("transform", existing), fields)
            if diff:
                changes.append({"entity": "transform", "action": "update", "name": item["name"],
                                "fields": diff})

    for key, value in (payload.get("settings") or {}).items():
        if key not in settings_service.KNOWN:
            skipped.append(f"setting {key}: unknown key")
            continue
        errors = settings_service.validate_value(key, value)
        if errors:
            skipped.append(f"setting {key}: {'; '.join(errors)}")
            continue
        existing = settings.get(key)
        if existing is None or existing.value != value:
            changes.append({"entity": "setting", "action": "update", "name": key,
                            "fields": {"value": value}})

    return {
        "schema_version": SCHEMA_VERSION,
        "changes": changes,
        "skipped": skipped,
        "summary": {
            "create": len([c for c in changes if c["action"] == "create"]),
            "update": len([c for c in changes if c["action"] == "update"]),
            "skipped": len(skipped),
        },
    }


def apply_import(session, payload: dict, actor: str) -> dict:
    """Apply the import (upsert only) and record one audit entry per change."""
    plan = plan_import(session, payload)

    sources = _rows_by_name(session, MwlSource)
    targets = _rows_by_name(session, PacsTarget)
    transforms = _rows_by_name(session, TransformRule)

    for item in payload.get("sources", []):
        row = sources.get(item["name"])
        before = audit.snapshot("source", row)
        if row is None:
            row = MwlSource(**item)
            session.add(row)
        else:
            for key, value in item.items():
                setattr(row, key, value)
        session.flush()
        audit.record(session, actor, "import.source", "source", row.id, before,
                     audit.snapshot("source", row))

    for item in payload.get("targets", []):
        row = targets.get(item["name"])
        before = audit.snapshot("target", row)
        if row is None:
            row = PacsTarget(**item)
            session.add(row)
        else:
            for key, value in item.items():
                setattr(row, key, value)
        session.flush()
        audit.record(session, actor, "import.target", "target", row.id, before,
                     audit.snapshot("target", row))

    # sources/targets may just have been created by this document
    sources.update(_rows_by_name(session, MwlSource))
    targets.update(_rows_by_name(session, PacsTarget))

    for item in payload.get("rules", []):
        src, tgt = sources.get(item["source"]), targets.get(item["target"])
        if src is None or tgt is None:
            continue
        row = session.scalars(
            select(RoutingRule).where(
                RoutingRule.source_id == src.id, RoutingRule.target_id == tgt.id
            )
        ).first()
        before = audit.snapshot("rule", row)
        if row is None:
            row = RoutingRule(source_id=src.id, target_id=tgt.id,
                              priority=item.get("priority", 100),
                              enabled=item.get("enabled", True))
            session.add(row)
        else:
            row.priority = item.get("priority", 100)
            row.enabled = item.get("enabled", True)
        session.flush()
        audit.record(session, actor, "import.rule", "rule", row.id, before,
                     audit.snapshot("rule", row))

    for item in payload.get("transforms", []):
        source_id = sources[item["source"]].id if item.get("source") else None
        target_id = targets[item["target"]].id if item.get("target") else None
        row = transforms.get(item["name"])
        before = audit.snapshot("transform", row)
        fields = {
            "enabled": item.get("enabled", True),
            "priority": item.get("priority", 100),
            "operations": _normalize_operations(item.get("operations", [])),
            "source_id": source_id,
            "target_id": target_id,
        }
        if row is None:
            row = TransformRule(name=item["name"], **fields)
            session.add(row)
        else:
            for key, value in fields.items():
                setattr(row, key, value)
        session.flush()
        audit.record(session, actor, "import.transform", "transform", row.id, before,
                     audit.snapshot("transform", row))

    for key, value in (payload.get("settings") or {}).items():
        if key not in settings_service.KNOWN or settings_service.validate_value(key, value):
            continue
        row = session.get(BrokerSetting, key)
        before = audit.snapshot("setting", row)
        if row is None:
            row = BrokerSetting(key=key, value=str(value))
            session.add(row)
        else:
            row.value = str(value)
        session.flush()
        audit.record(session, actor, "import.setting", "setting", None, before,
                     audit.snapshot("setting", row))

    session.commit()
    return plan
