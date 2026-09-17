"""REST API: CRUD for sources/targets/rules, logs, status.

All endpoints are sync `def` — they run in the FastAPI threadpool, which
keeps them consistent with the synchronous DIMSE handlers.
"""
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_session
from .echo import echo_one, snapshot
from .models import (
    MwlSource,
    PacsTarget,
    QueryLog,
    RoutingRule,
    SeenItem,
    StoreLog,
)
from .schemas import (
    AuditEntryOut,
    BreakerStateOut,
    CacheItemOut,
    CacheSourceOut,
    ConfigExportOut,
    ConfigImportIn,
    ImportPlanOut,
    RollbackOut,
    SimulateRouteIn,
    SimulateRouteOut,
    SimulateTransformIn,
    SimulateTransformOut,
    EchoResult,
    HealthOut,
    QueryLogOut,
    RuleIn,
    RuleOut,
    SettingOut,
    SettingUpdateIn,
    SourceIn,
    SourceOut,
    StatusOut,
    StoreLogOut,
    TargetIn,
    TargetOut,
    TransformIn,
    TransformOut,
)
from . import audit, breaker, cache, config_io, health_checks, settings_service, simulate, transforms
from .models import BrokerSetting, ConfigAudit, SeenItem, SourceBreaker, TransformRule

router = APIRouter(prefix="/api/v1")

_scp = None  # set by main.py for /status


def bind_scp(scp) -> None:
    global _scp
    _scp = scp


def scp_listening() -> bool:
    """Whether the DICOM SCP is up (used by /status and /healthz/ready)."""
    return _scp.listening if _scp is not None else False


def _db() -> Session:
    s = get_session()
    try:
        yield s
    finally:
        s.close()


_db_dep = Depends(_db)


def _actor(request: Request) -> str:
    return audit.actor_from(request.headers)


def _correlation(request: Request) -> str:
    return request.headers.get("X-Request-Id", "")[:64]


def _crud(router: APIRouter, path: str, model, in_schema, out_schema, kind: str,
          before_delete=None):
    """Register list/create/get/update/delete for a model with `name`.

    `before_delete(session, row_id)` runs inside the same transaction and
    removes dependent rows (rules/transforms/seen_items/breaker state) — a
    bare delete would violate the foreign keys on Postgres.
    """

    @router.get(
        path, response_model=list[out_schema], name=f"list_{path[1:]}",
        tags=[f"{path[1:]}"], summary=f"List {kind}s",
        response_description=f"All {kind}s ordered by ID.",
    )
    def _list(s: Session = _db_dep):
        return s.scalars(select(model).order_by(model.id)).all()

    @router.post(
        path, response_model=out_schema, status_code=201, name=f"create_{path[1:]}",
        tags=[f"{path[1:]}"], summary=f"Create a {kind}",
        response_description=f"The created {kind}.",
        responses={409: {"description": f"A {kind} with this name already exists."}},
    )
    def _create(
        request: Request,
        body: Annotated[in_schema, Body(description=f"{kind.capitalize()} definition.")],
        s: Session = _db_dep,
    ):
        if s.scalar(select(model).where(model.name == body.name)):
            raise HTTPException(409, f"{body.name} already exists")
        row = model(**body.model_dump())
        s.add(row)
        s.flush()
        audit.record(s, _actor(request), f"create.{kind}", kind, row.id,
                     None, audit.snapshot(kind, row), _correlation(request))
        s.commit()
        s.refresh(row)
        return row

    @router.put(
        path + "/{row_id}", response_model=out_schema, name=f"update_{path[1:]}",
        tags=[f"{path[1:]}"], summary=f"Update a {kind}",
        response_description=f"The updated {kind}.",
        responses={404: {"description": f"No {kind} with this ID."}},
    )
    def _update(
        request: Request,
        row_id: Annotated[int, Path(description=f"ID of the {kind} to update.")],
        body: Annotated[in_schema, Body(description=f"Complete {kind} definition (replace semantics).")],
        s: Session = _db_dep,
    ):
        row = s.get(model, row_id)
        if row is None:
            raise HTTPException(404, "not found")
        before = audit.snapshot(kind, row)
        for k, v in body.model_dump().items():
            setattr(row, k, v)
        s.flush()
        audit.record(s, _actor(request), f"update.{kind}", kind, row.id,
                     before, audit.snapshot(kind, row), _correlation(request))
        s.commit()
        s.refresh(row)
        return row

    @router.delete(
        path + "/{row_id}", status_code=204, name=f"delete_{path[1:]}",
        tags=[f"{path[1:]}"], summary=f"Delete a {kind}",
        response_description=f"The {kind} was deleted.",
        responses={404: {"description": f"No {kind} with this ID."}},
    )
    def _delete(
        request: Request,
        row_id: Annotated[int, Path(description=f"ID of the {kind} to delete.")],
        s: Session = _db_dep,
    ):
        row = s.get(model, row_id)
        if row is None:
            raise HTTPException(404, "not found")
        before = audit.snapshot(kind, row)
        if before_delete is not None:
            before_delete(s, row_id)
        s.delete(row)
        audit.record(s, _actor(request), f"delete.{kind}", kind, row_id,
                     before, None, _correlation(request))
        s.commit()


def _drop_source_dependencies(s: Session, source_id: int) -> None:
    """Remove everything that references a source before it is deleted."""
    for model, column in (
        (RoutingRule, RoutingRule.source_id),
        (TransformRule, TransformRule.source_id),
        (SeenItem, SeenItem.source_id),
        (SourceBreaker, SourceBreaker.source_id),
    ):
        for row in s.scalars(select(model).where(column == source_id)).all():
            s.delete(row)
    s.flush()


def _drop_target_dependencies(s: Session, target_id: int) -> None:
    """Remove everything that references a target before it is deleted."""
    for model, column in (
        (RoutingRule, RoutingRule.target_id),
        (TransformRule, TransformRule.target_id),
    ):
        for row in s.scalars(select(model).where(column == target_id)).all():
            s.delete(row)
    s.flush()


_crud(router, "/sources", MwlSource, SourceIn, SourceOut, "source",
      before_delete=_drop_source_dependencies)
_crud(router, "/targets", PacsTarget, TargetIn, TargetOut, "target",
      before_delete=_drop_target_dependencies)


# ── Routing rules ──────────────────────────────────────────────────────


@router.get(
    "/rules", response_model=list[RuleOut], tags=["rules"],
    summary="List routing rules",
    response_description="All rules ordered by priority, then ID.",
)
def list_rules(s: Session = _db_dep):
    return s.scalars(select(RoutingRule).order_by(RoutingRule.priority, RoutingRule.id)).all()


@router.post(
    "/rules", response_model=RuleOut, status_code=201, tags=["rules"],
    summary="Create a routing rule",
    response_description="The created rule.",
    responses={404: {"description": "Referenced source or target does not exist."}},
)
def create_rule(
    request: Request,
    body: Annotated[RuleIn, Body(description="Routing rule definition.")],
    s: Session = _db_dep,
):
    for mid, label in ((body.source_id, "source"), (body.target_id, "target")):
        model = MwlSource if label == "source" else PacsTarget
        if s.get(model, mid) is None:
            raise HTTPException(404, f"{label} {mid} not found")
    row = RoutingRule(**body.model_dump())
    s.add(row)
    s.flush()
    audit.record(s, _actor(request), "create.rule", "rule", row.id, None,
                 audit.snapshot("rule", row), _correlation(request))
    s.commit()
    s.refresh(row)
    return row


@router.put(
    "/rules/{rule_id}", response_model=RuleOut, tags=["rules"],
    summary="Update a routing rule",
    response_description="The updated rule.",
    responses={404: {"description": "No rule with this ID."}},
)
def update_rule(
    request: Request,
    rule_id: Annotated[int, Path(description="ID of the rule to update.")],
    body: Annotated[RuleIn, Body(description="Routing rule definition (replace semantics).")],
    s: Session = _db_dep,
):
    row = s.get(RoutingRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    before = audit.snapshot("rule", row)
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    s.flush()
    audit.record(s, _actor(request), "update.rule", "rule", row.id, before,
                 audit.snapshot("rule", row), _correlation(request))
    s.commit()
    s.refresh(row)
    return row


@router.delete(
    "/rules/{rule_id}", status_code=204, tags=["rules"],
    summary="Delete a routing rule",
    response_description="The rule was deleted.",
    responses={404: {"description": "No rule with this ID."}},
)
def delete_rule(
    request: Request,
    rule_id: Annotated[int, Path(description="ID of the rule to delete.")],
    s: Session = _db_dep,
):
    row = s.get(RoutingRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    before = audit.snapshot("rule", row)
    s.delete(row)
    audit.record(s, _actor(request), "delete.rule", "rule", rule_id, before,
                 None, _correlation(request))
    s.commit()


# ── Transform rules (DICOM attribute modify on forward) ────────────────


def _ops_payload(body: TransformIn) -> list[dict]:
    """Validate the operations and return them as plain JSON-ready dicts."""
    ops = [op.model_dump(exclude_none=True) for op in body.operations]
    errors = transforms.validate_operations(ops)
    if errors:
        raise HTTPException(422, detail=errors)
    return ops


def _check_scope(s: Session, body: TransformIn) -> None:
    for mid, model, label in (
        (body.source_id, MwlSource, "source"), (body.target_id, PacsTarget, "target"),
    ):
        if mid is not None and s.get(model, mid) is None:
            raise HTTPException(404, f"{label} {mid} not found")


@router.get(
    "/transforms", response_model=list[TransformOut], tags=["transforms"],
    summary="List transform rules",
    response_description="All rules ordered by priority, then ID.",
)
def list_transforms(s: Session = _db_dep):
    return s.scalars(
        select(TransformRule).order_by(TransformRule.priority, TransformRule.id)
    ).all()


@router.post(
    "/transforms", response_model=TransformOut, status_code=201, tags=["transforms"],
    summary="Create a transform rule",
    response_description="The created rule.",
    responses={
        404: {"description": "Referenced source or target does not exist."},
        409: {"description": "A rule with this name already exists."},
        422: {"description": "Invalid DICOM keyword / operation (details in `detail`)."},
    },
)
def create_transform(
    request: Request,
    body: Annotated[TransformIn, Body(description="Transform rule definition (operations are validated against the DICOM dictionary).")],
    s: Session = _db_dep,
):
    if s.scalar(select(TransformRule).where(TransformRule.name == body.name)):
        raise HTTPException(409, f"{body.name} already exists")
    _check_scope(s, body)
    row = TransformRule(
        name=body.name, enabled=body.enabled, priority=body.priority,
        source_id=body.source_id, target_id=body.target_id,
        operations=_ops_payload(body),
    )
    s.add(row)
    s.flush()
    audit.record(s, _actor(request), "create.transform", "transform", row.id, None,
                 audit.snapshot("transform", row), _correlation(request))
    s.commit()
    s.refresh(row)
    return row


@router.put(
    "/transforms/{rule_id}", response_model=TransformOut, tags=["transforms"],
    summary="Update a transform rule",
    response_description="The updated rule.",
    responses={
        404: {"description": "No rule with this ID (or scope row missing)."},
        422: {"description": "Invalid DICOM keyword / operation."},
    },
)
def update_transform(
    request: Request,
    rule_id: Annotated[int, Path(description="ID of the transform rule to update.")],
    body: Annotated[TransformIn, Body(description="Transform rule definition (replace semantics).")],
    s: Session = _db_dep,
):
    row = s.get(TransformRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    _check_scope(s, body)
    before = audit.snapshot("transform", row)
    row.name = body.name
    row.enabled = body.enabled
    row.priority = body.priority
    row.source_id = body.source_id
    row.target_id = body.target_id
    row.operations = _ops_payload(body)
    s.flush()
    audit.record(s, _actor(request), "update.transform", "transform", row.id, before,
                 audit.snapshot("transform", row), _correlation(request))
    s.commit()
    s.refresh(row)
    return row


@router.delete(
    "/transforms/{rule_id}", status_code=204, tags=["transforms"],
    summary="Delete a transform rule",
    response_description="The transform rule was deleted.",
    responses={404: {"description": "No rule with this ID."}},
)
def delete_transform(
    request: Request,
    rule_id: Annotated[int, Path(description="ID of the transform rule to delete.")],
    s: Session = _db_dep,
):
    row = s.get(TransformRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    before = audit.snapshot("transform", row)
    s.delete(row)
    audit.record(s, _actor(request), "delete.transform", "transform", rule_id, before,
                 None, _correlation(request))
    s.commit()


# ── Runtime settings (DB override over ENV default) ────────────────────


@router.get(
    "/settings", response_model=list[SettingOut], tags=["settings"],
    summary="List runtime settings",
    description="Effective value, the deployment ENV default and which one is "
                "currently active (`source`).",
    response_description="All known settings.",
)
def list_settings():
    return settings_service.list_all()


@router.put(
    "/settings/{key}", response_model=SettingOut, tags=["settings"],
    summary="Override a setting",
    description="Stores a runtime override; the ENV value stays the fallback "
                "and is restored by DELETE.",
    response_description="The setting with its new effective value.",
    responses={
        404: {"description": "Unknown setting key."},
        422: {"description": "Invalid value for this setting type."},
    },
)
def update_setting(
    request: Request,
    key: Annotated[str, Path(description="Setting key (see GET /settings for the allowlist).")],
    body: Annotated[SettingUpdateIn, Body(description="New value — validated against the setting type.")],
    s: Session = _db_dep,
):
    if key not in settings_service.KNOWN:
        raise HTTPException(404, f"unknown setting {key!r}")
    errors = settings_service.validate_value(key, body.value)
    if errors:
        raise HTTPException(422, detail=errors)
    before = audit.snapshot("setting", s.get(BrokerSetting, key))
    settings_service.set_value(key, body.value, session=s)
    audit.record(s, _actor(request), "update.setting", "setting", None, before,
                 {"key": key, "value": body.value}, _correlation(request))
    s.commit()
    return next(s2 for s2 in settings_service.list_all() if s2["key"] == key)


@router.delete(
    "/settings/{key}", status_code=204, tags=["settings"],
    summary="Reset a setting to the ENV default",
    response_description="The override was removed; the ENV default applies again.",
    responses={404: {"description": "Unknown setting key."}},
)
def reset_setting(
    request: Request,
    key: Annotated[str, Path(description="Setting key whose override should be removed.")],
    s: Session = _db_dep,
):
    if key not in settings_service.KNOWN:
        raise HTTPException(404, f"unknown setting {key!r}")
    before = audit.snapshot("setting", s.get(BrokerSetting, key))
    settings_service.reset(key)
    audit.record(s, _actor(request), "reset.setting", "setting", None, before,
                 None, _correlation(request))
    s.commit()


# ── Worklist cache ─────────────────────────────────────────────────────


@router.get(
    "/cache/stats", response_model=list[CacheSourceOut], tags=["cache"],
    summary="Worklist cache state",
    description="Cached worklist snapshots per source. The cache bridges an "
                "unreachable RIS; a live answer always replaces the snapshot, "
                "so completed orders disappear immediately.",
    response_description="One entry per source with item count, age and state.",
)
def cache_stats(s: Session = _db_dep):
    return cache.stats()


@router.get(
    "/cache/items", response_model=list[CacheItemOut], tags=["cache"],
    summary="Cached worklist items",
    description="Metadata of the cached items (source, accession, study UID, "
                "modality, station, SPS status, age). Patient identifiers are "
                "deliberately not exposed.",
    response_description="Cached items, newest first.",
)
def cache_items(
    s: Session = _db_dep,
    source_id: int | None = Query(default=None, description="Only items of this source."),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of items."),
):
    return cache.items(source_id, limit)


@router.delete(
    "/cache", tags=["cache"], status_code=204,
    summary="Clear the whole worklist cache",
    description="Removes every cached snapshot. The next queries go to the "
                "upstream again; an outage can no longer be bridged until then.",
    response_description="The cache was cleared.",
)
def clear_cache(s: Session = _db_dep):
    cache.clear()


@router.delete(
    "/cache/sources/{source_id}", tags=["cache"], status_code=204,
    summary="Clear one source's cache",
    description="Removes the cached snapshot of a single source.",
    response_description="The source's cache was cleared.",
    responses={404: {"description": "No source with this ID."}},
)
def clear_source_cache(
    source_id: Annotated[int, Path(description="ID of the source whose cache is cleared.")],
    s: Session = _db_dep,
):
    if s.get(MwlSource, source_id) is None:
        raise HTTPException(404, "not found")
    cache.clear(source_id)


# ── Change log, export/import, rollback ────────────────────────────────


@router.get(
    "/audit/config", response_model=list[AuditEntryOut], tags=["audit"],
    summary="Configuration change log",
    description="Every configuration mutation with its before/after snapshot "
                "(basis for the diff view and for rollback).",
    response_description="Change-log entries, newest first.",
)
def list_config_audit(
    s: Session = _db_dep,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of entries."),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip."),
    entity: str | None = Query(default=None, description="Only entries for this entity (source | target | rule | transform | setting)."),
):
    return audit.list_entries(s, entity=entity, limit=limit, offset=offset)


@router.get(
    "/config/export", response_model=ConfigExportOut, tags=["config"],
    summary="Export the configuration",
    description="Portable document: rules and modify rules reference sources and "
                "targets by name, so it can be imported into another environment.",
    response_description="The complete broker configuration.",
)
def export_configuration(s: Session = _db_dep):
    return config_io.export_config(s)


@router.post(
    "/config/import", response_model=ImportPlanOut, tags=["config"],
    summary="Import a configuration (dry-run by default)",
    description="Upsert-only: existing entries are updated by name, missing ones "
                "are created. Nothing is ever deleted. With `dry_run=true` "
                "(the default) the response is the diff instead of applying it.",
    response_description="The planned (dry-run) or applied changes plus a summary.",
    responses={422: {"description": "Unsupported `schema_version` or invalid document."}},
)
def import_configuration(
    request: Request,
    body: ConfigImportIn,
    dry_run: bool = Query(default=True, description="Only compute the diff; write nothing."),
    s: Session = _db_dep,
):
    if body.schema_version != config_io.SCHEMA_VERSION:
        raise HTTPException(422, [
            f"schema_version {body.schema_version} is not supported "
            f"(this broker expects {config_io.SCHEMA_VERSION})"
        ])
    payload = body.model_dump()
    if dry_run:
        return {**config_io.plan_import(s, payload), "dry_run": True}
    return {**config_io.apply_import(s, payload, _actor(request)), "dry_run": False}


@router.post(
    "/config/rollback/{audit_id}", response_model=RollbackOut, tags=["config"],
    summary="Roll a configuration change back",
    description="Restores the state before that change-log entry: an update is "
                "reverted, a deletion is re-created, a creation is removed. The "
                "rollback itself is recorded in the change log.",
    response_description="What the rollback did.",
    responses={
        404: {"description": "No change-log entry with this ID."},
        422: {"description": "The entry cannot be rolled back."},
    },
)
def rollback_configuration(
    request: Request,
    audit_id: Annotated[int, Path(description="ID of the change-log entry to roll back.")],
    s: Session = _db_dep,
):
    entry = s.get(ConfigAudit, audit_id)
    if entry is None:
        raise HTTPException(404, "not found")
    serializer = audit.SERIALIZERS.get(entry.entity)
    if serializer is None:
        raise HTTPException(422, f"entity {entry.entity!r} cannot be rolled back")
    model, _ = serializer

    if entry.entity == "setting":
        key = (entry.before_json or entry.after_json or {}).get("key", "")
        row = s.get(BrokerSetting, key)
        before_now = audit.snapshot("setting", row)
        if entry.before_json is None:
            if row is not None:
                s.delete(row)
            action, after = "delete", None
        elif row is None:
            row = BrokerSetting(**entry.before_json)
            s.add(row)
            action = "recreate"
        else:
            row.value = entry.before_json["value"]
            action = "restore"
        s.flush()
        after = audit.snapshot("setting", row) if entry.before_json is not None else None
    else:
        row = s.get(model, entry.entity_id) if entry.entity_id is not None else None
        before_now = audit.snapshot(entry.entity, row)
        if entry.before_json is None:          # the change created it → remove it
            if row is not None:
                s.delete(row)
            action, after = "delete", None
        elif row is None:                      # the change deleted it → recreate it
            row = model(**entry.before_json)
            s.add(row)
            s.flush()
            action, after = "recreate", audit.snapshot(entry.entity, row)
        else:                                  # the change updated it → restore
            for key_name, value in entry.before_json.items():
                setattr(row, key_name, value)
            action, after = "restore", audit.snapshot(entry.entity, row)

    audit.record(s, _actor(request), f"rollback.{entry.entity}", entry.entity,
                 entry.entity_id, before_now, after, _correlation(request))
    s.commit()
    return {
        "audit_id": audit_id,
        "entity": entry.entity,
        "action": action,
        "message": f"{action} {entry.entity} (change-log entry {audit_id})",
    }


# ── Simulation (dry-run) ───────────────────────────────────────────────


@router.post(
    "/simulate/route", response_model=SimulateRouteOut, tags=["simulation"],
    summary="Simulate store routing",
    description="Runs the **same** resolver as the live C-STORE path: which "
                "target would receive an instance with this accession/study, "
                "and which rule decided it. Nothing is sent or stored.",
    response_description="The routing decision with its reason.",
)
def simulate_routing(body: SimulateRouteIn, s: Session = _db_dep):
    return simulate.simulate_route(s, body.accession, body.study_uid)


@router.post(
    "/simulate/transform", response_model=SimulateTransformOut, tags=["simulation"],
    summary="Simulate the modify rules",
    description="Applies the modify rules that would match this case to the "
                "supplied tag values and returns the tag-level diff. Uses the "
                "same functions as the forwarding path.",
    response_description="The routing decision plus the tag changes and any failing operations.",
)
def simulate_transformation(body: SimulateTransformIn, s: Session = _db_dep):
    return simulate.simulate_transform(
        s, body.values, body.accession, body.study_uid, body.source_id, body.target_id,
    )


# ── Logs ───────────────────────────────────────────────────────────────


@router.get(
    "/logs/queries", response_model=list[QueryLogOut], tags=["logs"],
    summary="C-FIND query log",
    response_description="Query log entries, newest first.",
)
def query_logs(
    s: Session = _db_dep,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of entries."),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip."),
    calling_aet: str | None = Query(default=None, description="Only entries from this calling AE title."),
    status: str | None = Query(default=None, description="Only entries with this status (success | partial | failed)."),
):
    q = select(QueryLog).order_by(QueryLog.ts.desc()).limit(limit).offset(offset)
    if calling_aet:
        q = q.where(QueryLog.calling_aet == calling_aet)
    if status:
        q = q.where(QueryLog.status == status)
    return s.scalars(q).all()


@router.get(
    "/logs/stores", response_model=list[StoreLogOut], tags=["logs"],
    summary="C-STORE forward log",
    response_description="Store log entries, newest first.",
)
def store_logs(
    s: Session = _db_dep,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of entries."),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip."),
    status: str | None = Query(default=None, description="Only entries with this status (success | failed | unrouted)."),
):
    q = select(StoreLog).order_by(StoreLog.ts.desc()).limit(limit).offset(offset)
    if status:
        q = q.where(StoreLog.status == status)
    return s.scalars(q).all()


# ── Echo + status ──────────────────────────────────────────────────────


@router.post(
    "/sources/{source_id}/echo", response_model=EchoResult, tags=["monitoring"],
    summary="C-ECHO a source now",
    response_description="Echo result with RTT (or the error detail).",
    responses={404: {"description": "No source with this ID."}},
)
def echo_source(
    source_id: Annotated[int, Path(description="ID of the source to C-ECHO.")],
    s: Session = _db_dep,
):
    row = s.get(MwlSource, source_id)
    if row is None:
        raise HTTPException(404, "not found")
    return echo_one("source", row)


@router.post(
    "/targets/{target_id}/echo", response_model=EchoResult, tags=["monitoring"],
    summary="C-ECHO a target now",
    response_description="Echo result with RTT (or the error detail).",
    responses={404: {"description": "No target with this ID."}},
)
def echo_target(
    target_id: Annotated[int, Path(description="ID of the target to C-ECHO.")],
    s: Session = _db_dep,
):
    row = s.get(PacsTarget, target_id)
    if row is None:
        raise HTTPException(404, "not found")
    return echo_one("target", row)


@router.post(
    "/sources/{source_id}/reset-breaker", response_model=BreakerStateOut,
    tags=["monitoring"],
    summary="Reset a source's circuit breaker",
    description="Puts the source back into the C-FIND fan-out immediately "
                "instead of waiting for the open window to expire.",
    response_description="The breaker state after the reset (closed).",
    responses={404: {"description": "No source with this ID."}},
)
def reset_breaker(
    source_id: Annotated[int, Path(description="ID of the source whose breaker is reset.")],
    s: Session = _db_dep,
):
    row = s.get(MwlSource, source_id)
    if row is None:
        raise HTTPException(404, "not found")
    breaker.reset(source_id)
    state = breaker.snapshot().get(source_id)
    return {
        "source_id": source_id,
        "name": row.name,
        "state": (state or {}).get("state", breaker.STATE_CLOSED),
        "failures": (state or {}).get("failures", 0),
        "retry_in_s": (state or {}).get("retry_in_s"),
        "last_error": (state or {}).get("last_error", ""),
    }


@router.get(
    "/health/config", response_model=HealthOut, tags=["monitoring"],
    summary="Configuration consistency checks",
    description="Checks the broker configuration for the typical production "
                "mistakes (no default target, rules on disabled nodes, dead "
                "sources, open circuit breakers, empty AET allowlist, …).",
    response_description="Findings sorted by severity plus a severity summary.",
)
def health_config(s: Session = _db_dep):
    from .config import get_settings

    findings = health_checks.config_findings(s, get_settings())
    return {"findings": findings, "summary": health_checks.summary(findings)}


@router.get(
    "/status", response_model=StatusOut, tags=["monitoring"],
    summary="Broker status snapshot",
    description="SCP/DB health, per-source and per-target echo results "
                "(with RTT), and query/store/seen_items counters. "
                "Polled by the OE3 broker dashboard.",
    response_description="Current status snapshot.",
)
def status(s: Session = _db_dep):
    snap = snapshot()
    from .db import check_db

    breakers = breaker.snapshot()

    def with_echo(model_rows, kind):
        by_id = {e["id"]: e for e in snap[kind]}
        out = []
        for r in model_rows:
            e = dict(by_id.get(r.id) or {
                "kind": kind, "id": r.id, "name": r.name,
                "ok": False, "rtt_ms": None, "last_check": None, "error": "never checked",
            })
            if kind == "source":
                state = breakers.get(r.id) or {}
                e["breaker_state"] = state.get("state", breaker.STATE_CLOSED)
                e["breaker_retry_in_s"] = state.get("retry_in_s")
            out.append(e)
        return out

    return {
        "scp_listening": _scp.listening if _scp is not None else False,
        "db_ok": check_db(),
        "sources": with_echo(s.scalars(select(MwlSource).order_by(MwlSource.id)).all(), "source"),
        "targets": with_echo(s.scalars(select(PacsTarget).order_by(PacsTarget.id)).all(), "target"),
        "counts": {
            "queries": s.scalar(select(func.count(QueryLog.id))) or 0,
            "stores": s.scalar(select(func.count(StoreLog.id))) or 0,
            "seen_items": s.scalar(select(func.count(SeenItem.id))) or 0,
        },
    }
