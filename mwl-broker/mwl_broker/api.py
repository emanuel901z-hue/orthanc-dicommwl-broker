"""REST API: CRUD for sources/targets/rules, logs, status.

All endpoints are sync `def` — they run in the FastAPI threadpool, which
keeps them consistent with the synchronous DIMSE handlers.
"""

import logging
from datetime import datetime, timezone

from pydicom.dataset import Dataset
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_session, session_factory
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
    AtnaSampleOut,
    AtnaStatsOut,
    AtnaTestOut,
    Hl7MessageOut,
    Hl7ParseOut,
    LocalItemIn,
    LocalItemOut,
    AuditEntryOut,
    BreakerStateOut,
    CacheItemOut,
    CacheSourceOut,
    ConfigExportOut,
    ConfigImportIn,
    ImportPlanOut,
    RollbackOut,
    NotifyEventOut,
    NotifyTestOut,
    SpoolItemOut,
    SpoolRetryOut,
    SpoolStatsOut,
    StationPreviewOut,
    StationSimulateIn,
    StationsSimulateIn,
    StationRuleIn,
    StationRuleOut,
    RbacStatusOut,
    RetentionPurgeOut,
    RetentionOut,
    RetentionTableOut,
    RbacStatusOut,
    TlsOverviewOut,
    TlsSelfSignedIn,
    TlsSelfSignedOut,
    TlsTestIn,
    TlsTestOut,
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
    StatsOut,
    StatusOut,
    StoreLogOut,
    TargetIn,
    TargetOut,
    TransformIn,
    TransformOut,
    WorklistPreviewIn,
    WorklistPreviewOut,
    SourceQueryIn,
    SourceQueryOut,
    Hl7MessageDetailOut,
    Hl7ReprocessOut,
    CacheRefreshOut,
    TlsUploadIn,
    TlsUploadOut,
    MppsStepOut,
    MppsStatsOut,
    MppsForwardOut,
    MergeRuleIn,
    MergeRuleOut,
    Hl7FieldMapIn,
    Hl7FieldMapOut,
)
from . import (atna, audit, breaker, cache, config_io, health_checks, hl7, hl7_mapping,
               merge_rules, mpps, stats, ups,
               local_worklist, metrics, notify, rbac, retention, settings_service,
               simulate, spool, station_rules, tls, transforms)
from .models import (BrokerSetting, ConfigAudit, Hl7Message, LocalWorklistItem,
                     SeenItem, SourceBreaker, StationRule, TransformRule)

router = APIRouter(prefix="/api/v1")

log = logging.getLogger("mwl_broker.api")

# process start — the status endpoint reports uptime from here
_STARTED_AT = datetime.now(timezone.utc)

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


# ── shared response documentation ──────────────────────────────────────
# Written once and reused: FastAPI would otherwise show its generic
# "Validation Error" text, and integrators need to know what a failure looks
# like — `detail` is a plain sentence for the broker's own checks (422) and a
# list of fields for schema errors.
VALIDATION_422 = {
    422: {
        "description": "Invalid value. `detail` is a list of the offending fields "
                       "for schema errors, a plain sentence for the broker's own "
                       "checks (e.g. a host name with spaces).",
    },
}
READ_ONLY_403 = {
    403: {
        "description": "The caller is read-only: the write role is missing in the "
                       "roles header (see `GET /rbac/status`).",
    },
}
NOT_FOUND_404 = {404: {"description": "No row with this ID."}}
CONFLICT_409 = {409: {"description": "A row with this name already exists."}}


def _docs(*parts: dict) -> dict:
    """Merge response documentation blocks (later ones win)."""
    merged: dict = {}
    for part in parts:
        merged.update(part)
    return merged


def _actor(request: Request) -> str:
    return audit.actor_from(request.headers)


def _parse_since(value: str) -> datetime:
    """Parse an ISO date or timestamp into an aware UTC datetime.

    Accepts "2026-09-20" and "2026-09-20T08:00" (what an operator types) and
    raises a 422 with a plain sentence instead of a stack trace.
    """
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise HTTPException(422, f"'{value}' is not a valid date or timestamp "
                                 "(use 2026-09-20 or 2026-09-20T08:00).")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _identifier_from_preview(body) -> Dataset:
    """Build the C-FIND identifier the preview runs (same fields as a modality)."""
    identifier = Dataset()
    if getattr(body, "accession", ""):
        identifier.AccessionNumber = body.accession
    if getattr(body, "study_uid", ""):
        identifier.StudyInstanceUID = body.study_uid
    if getattr(body, "patient_id", ""):
        identifier.PatientID = body.patient_id
    sps = Dataset()
    if getattr(body, "modality", ""):
        sps.Modality = body.modality
    if getattr(body, "scheduled_date", ""):
        sps.ScheduledProcedureStepStartDate = body.scheduled_date
    if getattr(body, "station_aet", ""):
        sps.ScheduledStationAETitle = body.station_aet
    identifier.ScheduledProcedureStepSequence = [sps]
    return identifier


def _check_merge_rule(body) -> None:
    """A rule must name a real DICOM attribute and at least one known source."""
    from pydicom.datadict import tag_for_keyword

    if tag_for_keyword(body.tag) is None:
        raise HTTPException(422, [f"'{body.tag}' is not a DICOM attribute name "
                                  "(use the keyword, e.g. PatientName)"])
    wanted = [s.strip() for s in body.sources if s.strip()]
    if not wanted:
        raise HTTPException(422, ["at least one source is required"])
    with session_factory()() as s:
        known = {name for name in s.scalars(select(MwlSource.name)).all()}
    unknown = [name for name in wanted if name not in known and name != "local"]
    if unknown:
        raise HTTPException(422, [f"unknown source(s): {', '.join(unknown)} "
                                  "(configure them under Upstream sources first)"])


def _check_hl7_map(body) -> None:
    """A mapping must name a real HL7 segment, a field number and a DICOM attribute."""
    from pydicom.datadict import tag_for_keyword

    segment = (body.segment or "").strip().upper()
    if len(segment) != 3 or not segment.isalpha():
        raise HTTPException(422, [f"'{body.segment}' is not an HL7 segment (three letters, e.g. OBR)"])
    if body.field < 1 or body.field > 200:
        raise HTTPException(422, ["the HL7 field number must be between 1 and 200"])
    if body.component < 0 or body.component > 50:
        raise HTTPException(422, ["the component index must be between 0 and 50"])
    if tag_for_keyword(body.target_tag) is None:
        raise HTTPException(422, [f"'{body.target_tag}' is not a DICOM attribute name "
                                  "(use the keyword, e.g. ScheduledStationAETitle)"])


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
        description=f"Every {kind} in configuration order (by ID). Reading never "
                    f"needs the write role — only changes do.",
        response_description=f"All {kind}s ordered by ID.",
        responses=_docs(VALIDATION_422),
    )
    def _list(s: Session = _db_dep):
        return s.scalars(select(model).order_by(model.id)).all()

    def _check_node(body) -> None:
        """Nonsense in a DICOM node never works — reject it with a clear message.

        Only on input: an old row that predates the rule must still be listable.
        """
        if kind not in ("source", "target"):
            return
        from .schemas import validate_node_fields

        errors = validate_node_fields(
            getattr(body, "host", ""), getattr(body, "aet", ""),
            getattr(body, "calling_aet", None),
        )
        if errors:
            raise HTTPException(422, "; ".join(errors))

    @router.get(
        path + "/{row_id}", response_model=out_schema, name=f"get_{path[1:]}",
        tags=[f"{path[1:]}"], summary=f"Read one {kind}",
        description=f"One {kind} by ID — for scripts and integrations that should "
                    f"not fetch the whole list.",
        response_description=f"The {kind}.",
        responses=_docs(VALIDATION_422, NOT_FOUND_404),
    )
    def _get_one(
        row_id: Annotated[int, Path(description=f"ID of the {kind}.")],
        s: Session = _db_dep,
    ):
        row = s.get(model, row_id)
        if row is None:
            raise HTTPException(404, "not found")
        return row

    @router.post(
        path, response_model=out_schema, status_code=201, name=f"create_{path[1:]}",
        tags=[f"{path[1:]}"], summary=f"Create a {kind}",
        description=f"Adds a {kind}. The change is written to the audit log with "
                    f"the actor from the audit header.",
        response_description=f"The created {kind}.",
        responses=_docs(VALIDATION_422, READ_ONLY_403, CONFLICT_409),
    )
    def _create(
        request: Request,
        body: Annotated[in_schema, Body(description=f"{kind.capitalize()} definition.")],
        s: Session = _db_dep,
    ):
        _check_node(body)
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
        description=f"Replaces the whole {kind} (send every field). The previous "
                    f"state is kept in the change log and can be rolled back.",
        response_description=f"The updated {kind}.",
        responses=_docs(VALIDATION_422, READ_ONLY_403, NOT_FOUND_404),
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
        _check_node(body)
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
        description=f"Removes the {kind} together with everything that depends on "
                    f"it (routing rules, modify rules, history). The response is "
                    f"empty; the change log keeps the previous state.",
        response_description=f"The {kind} was deleted.",
        responses=_docs(VALIDATION_422, READ_ONLY_403, NOT_FOUND_404),
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
_crud(router, "/station-rules", StationRule, StationRuleIn, StationRuleOut, "station")


# ── Routing rules ──────────────────────────────────────────────────────


@router.get(
    "/rules", response_model=list[RuleOut], tags=["rules"],
    summary="List routing rules",
    description="Every routing rule. A rule decides which PACS receives images "
                "from which source; without a matching rule the default target is "
                "used. Read-only callers may list.",
    response_description="All rules ordered by priority, then ID.",
)
def list_rules(s: Session = _db_dep):
    return s.scalars(select(RoutingRule).order_by(RoutingRule.priority, RoutingRule.id)).all()


@router.post(
    "/rules", response_model=RuleOut, status_code=201, tags=["rules"],
    summary="Create a routing rule",
    description="Adds a rule. The same source and target pair cannot be routed "
                "twice — a duplicate is rejected so the result stays predictable.",
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


@router.get(
    "/rules/{rule_id}", response_model=RuleOut, tags=["rules"],
    summary="Read one routing rule",
    description="One routing rule by ID — for scripts and integrations that should not "
                "fetch the whole list.",
    response_description="The routing rule.",
    responses={404: {"description": "No routing rule with this ID."}},
)
def get_rules_rule(
    rule_id: Annotated[int, Path(description="ID of the routing rule.")],
    s: Session = _db_dep,
):
    row = s.get(RoutingRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    return row


@router.put(
    "/rules/{rule_id}", response_model=RuleOut, tags=["rules"],
    summary="Update a routing rule",
    description="Replaces the rule (source, target, priority, enabled). The "
                "previous state is kept in the change log.",
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
    description="Removes the rule; images then fall back to the default target. "
                "The change is audited.",
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
    "/merge-rules", response_model=list[MergeRuleOut], tags=["merge"],
    summary="List field-level merge rules",
    description="Rules that decide, per DICOM attribute, which source wins — "
                "demographics from the HIS feed while the study description comes "
                "from the RIS. Without a rule the whole item comes from the "
                "highest-priority source that knows the case.",
    response_description="All rules, ordered by tag.",
)
def list_merge_rules():
    return merge_rules.list_rules()


@router.post(
    "/merge-rules", response_model=MergeRuleOut, status_code=201, tags=["merge"],
    summary="Create or replace a merge rule",
    description="One rule per DICOM attribute; posting the same tag again "
                "replaces the order.",
    response_description="The stored rule.",
    responses=_docs(VALIDATION_422, READ_ONLY_403),
)
def create_merge_rule(
    request: Request,
    body: Annotated[MergeRuleIn, Body(description="Attribute and source order.")],
    s: Session = _db_dep,
):
    _check_merge_rule(body)
    row = merge_rules.upsert_rule(body.tag, body.sources, body.enabled)
    audit.record(s, _actor(request), "merge_rule.create", "merge_rule", row["id"],
                 None, {"tag": row["tag"], "sources": row["sources"]},
                 _correlation(request))
    s.commit()
    return row


@router.delete(
    "/merge-rules/{rule_id}", status_code=204, tags=["merge"],
    summary="Delete a merge rule",
    description="Removes the rule; the attribute falls back to the normal merge.",
    response_description="The rule was deleted.",
    responses=_docs(READ_ONLY_403, NOT_FOUND_404),
)
def delete_merge_rule(
    request: Request,
    rule_id: Annotated[int, Path(description="ID of the rule.")],
    s: Session = _db_dep,
):
    row = merge_rules.get_rule(rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    merge_rules.delete_rule(rule_id)
    audit.record(s, _actor(request), "merge_rule.delete", "merge_rule", rule_id,
                 {"tag": row["tag"], "sources": row["sources"]}, None,
                 _correlation(request))
    s.commit()


@router.get(
    "/transforms", response_model=list[TransformOut], tags=["transforms"],
    summary="List transform rules",
    description="Every DICOM attribute modification applied before forwarding. "
                "Read-only callers may list.",
    response_description="All rules ordered by priority, then ID.",
)
def list_transforms(s: Session = _db_dep):
    return s.scalars(
        select(TransformRule).order_by(TransformRule.priority, TransformRule.id)
    ).all()


@router.post(
    "/transforms", response_model=TransformOut, status_code=201, tags=["transforms"],
    summary="Create a transform rule",
    description="Adds a rule with one or more operations (set, remove, prefix, "
                "suffix, replace, copy). Keywords are validated against the DICOM "
                "data dictionary and UIDs cannot be modified.",
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


@router.get(
    "/transforms/{rule_id}", response_model=TransformOut, tags=["transforms"],
    summary="Read one modify rule",
    description="One modify (transform) rule by ID — for scripts and integrations "
                "that should not fetch the whole list.",
    response_description="The modify rule.",
    responses={404: {"description": "No modify rule with this ID."}},
)
def get_transform_rule(
    rule_id: Annotated[int, Path(description="ID of the modify rule.")],
    s: Session = _db_dep,
):
    row = s.get(TransformRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    return row


@router.put(
    "/transforms/{rule_id}", response_model=TransformOut, tags=["transforms"],
    summary="Update a transform rule",
    description="Replaces the rule including its operation list. The previous "
                "state is kept in the change log.",
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
    description="Removes the rule; forwarded images are then sent unchanged. The "
                "change is audited.",
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


@router.get(
    "/settings/{key}", response_model=SettingOut, tags=["settings"],
    summary="Read one setting",
    description="One setting with its effective value, the deployment default and "
                "the UI metadata (kind, bounds, choices).",
    response_description="The setting.",
    responses={404: {"description": "No setting with this key."}},
)
def get_setting(
    key: Annotated[str, Path(description="Setting key, e.g. echo_interval_s.")],
):
    row = next((entry for entry in settings_service.list_all() if entry["key"] == key), None)
    if row is None:
        raise HTTPException(404, "not found")
    return row


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
    description="Removes the UI override of one setting; the value from the "
                "deployment ENV applies again. The change is audited.",
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


# ── Access control (read vs. write) ────────────────────────────────────


@router.get(
    "/rbac/status", response_model=RbacStatusOut, tags=["monitoring"],
    summary="Access mode for this request",
    description="Whether configuration writes are allowed for the caller. The UI "
                "uses it to disable write actions instead of letting the operator "
                "run into 403 responses.",
    response_description="Enforcement state, the expected role and whether this caller may write.",
)
def rbac_status(request: Request, s: Session = _db_dep):
    return rbac.describe(request.headers)


# ── Retention ──────────────────────────────────────────────────────────


@router.get(
    "/retention", response_model=RetentionOut, tags=["retention"],
    summary="Retention overview",
    description="Row counts, oldest row and the configured retention per table. "
                "The change log is included but defaults to 'keep forever'.",
    response_description="Per-table retention state.",
)
def retention_overview(s: Session = _db_dep):
    return retention.overview()


@router.post(
    "/retention/purge", response_model=RetentionPurgeOut, tags=["retention"],
    summary="Run the retention cleanup now",
    description="Deletes everything older than the configured retention windows. "
                "A table with retention 0 is skipped — nothing is deleted implicitly. "
                "The action is audited.",
    response_description="Removed row counts per table.",
)
def retention_purge(
    request: Request,
    table: str | None = Query(default=None, description="Only this table (default: all)."),
    s: Session = _db_dep,
):
    if table is not None and table not in retention.TABLES:
        raise HTTPException(404, f"unknown table {table}")
    result = retention.purge(table)
    audit.record(s, _actor(request), "purge.retention", "setting", table, None,
                 result["removed"], _correlation(request))
    s.commit()
    return result


# ── DICOM TLS ──────────────────────────────────────────────────────────


@router.get(
    "/tls/overview", response_model=TlsOverviewOut, tags=["tls"],
    summary="TLS configuration and certificate state",
    description="Everything the operator needs to see about the configured "
                "certificates: does the file exist, whose is it, when does it "
                "expire, do key and certificate belong together. Private keys are "
                "never returned.",
    response_description="TLS state plus the per-file certificate and key details.",
)
def tls_overview(s: Session = _db_dep):
    tls.reload()          # the operator expects what is configured *now*
    return tls.overview()


@router.post(
    "/tls/self-signed", response_model=TlsSelfSignedOut, status_code=201, tags=["tls"],
    summary="Generate a self-signed certificate",
    description="Creates a certificate and key in the managed directory — the "
                "pragmatic path for a hospital without a PKI. Hand the public "
                "certificate to the modality/PACS vendor, then switch TLS on. "
                "The private key is written with mode 0600 and never leaves the broker.",
    response_description="Paths plus the public certificate (PEM) to hand over.",
    responses={422: {"description": "The request is invalid or the directory is not writable."}},
)
def tls_self_signed(
    request: Request,
    body: Annotated[TlsSelfSignedIn, Body(description="Name, validity and SANs of the certificate.")],
    s: Session = _db_dep,
):
    tls.reload()
    try:
        result = tls.generate_self_signed(body.common_name, body.days, body.san,
                                          body.is_ca, body.filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except OSError as exc:
        raise HTTPException(422, f"cannot write to {tls.directory()}: {exc}")
    audit.record(s, _actor(request), "generate.tls_certificate", "setting", None, None,
                 {"common_name": body.common_name, "days": body.days,
                  "path": result["certificate_path"]}, _correlation(request))
    s.commit()
    tls.publish_metrics()
    return result


@router.post(
    "/tls/upload", response_model=TlsUploadOut, tags=["tls"], status_code=201,
    summary="Install a certificate from the PKI",
    description="Stores a certificate/key pair (and optionally a CA bundle) that came "
                "from the hospital PKI. The pair is validated: the key must belong to "
                "the certificate and the certificate must be currently valid. The "
                "private key is written with mode 0600 and **never** returned. The "
                "change is written to the audit log.",
    response_description="Where the material was stored and what the certificate says.",
    responses=_docs(VALIDATION_422, READ_ONLY_403),
)
def upload_tls_certificate(
    request: Request,
    body: Annotated[TlsUploadIn, Body(description="Certificate, key and optional CA bundle (PEM).")],
    s: Session = _db_dep,
):
    try:
        stored = tls.store_uploaded(
            body.certificate_pem, body.key_pem, ca_pem=body.ca_pem,
            filename=body.filename, is_ca=body.is_ca,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    audit.record(s, _actor(request), "tls.upload", "tls", None,
                 {"filename": body.filename, "had_ca": bool(body.ca_pem)},
                 {"certificate_path": stored["certificate_path"],
                  "expires": (stored["certificate"] or {}).get("not_after", "")},
                 _correlation(request))
    s.commit()
    return stored


@router.post(
    "/tls/test", response_model=TlsTestOut, tags=["tls"],
    summary="Check a TLS endpoint",
    description="Performs a real handshake and reports protocol, cipher and the "
                "peer certificate; with `echo_aet` it also runs a C-ECHO over TLS. "
                "This is the check before a modality or PACS is switched over.",
    response_description="Handshake details, peer certificate and the optional C-ECHO result.",
)
def tls_test(request: Request, body: Annotated[TlsTestIn, Body(description="Endpoint to check.")]):
    tls.reload()
    result = tls.test_endpoint(body.host, body.port, body.verify, body.ca_file,
                               body.server_name, body.timeout_s)
    if body.echo_aet:
        try:
            from .upstream import c_echo

            c_echo(body.echo_aet, body.host, body.port,
                   body.calling_aet or settings_service.get_str("broker_aet") or "MWLBROKER",
                   timeout_s=body.timeout_s, tls=True,
                   tls_verify=body.verify if body.verify is not None else True)
            result["echo_ok"] = True
        except Exception as exc:
            result["echo_ok"] = False
            result["echo_error"] = str(exc)[:200]
    metrics.TLS_HANDSHAKE.labels(result="ok" if result["ok"] else "failed").inc()
    return result


# ── Local worklist items + HL7 ORD interface ───────────────────────────


def _local_snapshot(row: LocalWorklistItem) -> dict:
    return {
        "id": row.id, "accession": row.accession, "sps_id": row.sps_id,
        "patient_id": row.patient_id, "patient_name": row.patient_name,
        "birth_date": row.birth_date, "sex": row.sex, "modality": row.modality,
        "station_aet": row.station_aet,
        "procedure_description": row.procedure_description,
        "scheduled_date": row.scheduled_date, "scheduled_time": row.scheduled_time,
        "study_uid": row.study_uid, "sps_status": row.sps_status,
        "valid_until": row.valid_until, "enabled": row.enabled, "origin": row.origin,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


@router.get(
    "/local-items", response_model=list[LocalItemOut], tags=["local"],
    summary="Local worklist items",
    description="Items the broker adds to every C-FIND answer (emergencies, "
                "unscheduled exams). They are attributed to the pseudo source "
                "`local` and win the dedupe against the RIS.",
    response_description="Local items, newest first.",
)
def list_local_items(s: Session = _db_dep):
    rows = s.scalars(
        select(LocalWorklistItem).order_by(LocalWorklistItem.id.desc())
    ).all()
    return [_local_snapshot(row) for row in rows]


@router.post(
    "/local-items", response_model=LocalItemOut, status_code=201, tags=["local"],
    summary="Create a local worklist item",
    description="Adds an entry that is merged into every matching C-FIND. The "
                "default validity comes from `local_default_validity_days`.",
    response_description="The created item.",
    responses={409: {"description": "An item with this accession and SPS ID exists."}},
)
def create_local_item(
    request: Request,
    body: Annotated[LocalItemIn, Body(description="The worklist item to create.")],
    s: Session = _db_dep,
):
    existing = s.scalars(
        select(LocalWorklistItem).where(
            LocalWorklistItem.accession == body.accession,
            LocalWorklistItem.sps_id == body.sps_id,
        )
    ).first()
    if existing is not None:
        raise HTTPException(409, f"{body.accession}/{body.sps_id} already exists")
    values = body.model_dump()
    if values.get("valid_until") is None:
        values["valid_until"] = local_worklist.expiry_for()
    row = LocalWorklistItem(**values, origin="manual")
    s.add(row)
    s.flush()
    audit.record(s, _actor(request), "create.local_item", "local_item", row.id, None,
                 audit.snapshot("local_item", row), _correlation(request))
    s.commit()
    s.refresh(row)
    local_worklist.publish_metrics()
    return _local_snapshot(row)


@router.get(
    "/local-items/{item_id}", response_model=LocalItemOut, tags=["local-items"],
    summary="Read one local worklist item",
    description="One local worklist item by ID — for scripts and integrations that should not "
                "fetch the whole list.",
    response_description="The local worklist item.",
    responses={404: {"description": "No local worklist item with this ID."}},
)
def get_local_items_item(
    item_id: Annotated[int, Path(description="ID of the local worklist item.")],
    s: Session = _db_dep,
):
    row = s.get(LocalWorklistItem, item_id)
    if row is None:
        raise HTTPException(404, "not found")
    return row


@router.put(
    "/local-items/{item_id}", response_model=LocalItemOut, tags=["local"],
    summary="Update a local worklist item",
    description="Replaces a locally kept entry (emergency or unscheduled exam) "
                "that the broker mixes into every matching C-FIND answer.",
    response_description="The updated item.",
    responses={404: {"description": "No local item with this ID."}},
)
def update_local_item(
    request: Request,
    item_id: Annotated[int, Path(description="ID of the local item to update.")],
    body: Annotated[LocalItemIn, Body(description="Complete item definition (replace semantics).")],
    s: Session = _db_dep,
):
    row = s.get(LocalWorklistItem, item_id)
    if row is None:
        raise HTTPException(404, "not found")
    before = audit.snapshot("local_item", row)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    s.flush()
    audit.record(s, _actor(request), "update.local_item", "local_item", row.id, before,
                 audit.snapshot("local_item", row), _correlation(request))
    s.commit()
    s.refresh(row)
    return _local_snapshot(row)


@router.delete(
    "/local-items/{item_id}", tags=["local"], status_code=204,
    summary="Delete a local worklist item",
    description="The item disappears from the next worklist query.",
    response_description="The item was deleted.",
    responses={404: {"description": "No local item with this ID."}},
)
def delete_local_item(
    request: Request,
    item_id: Annotated[int, Path(description="ID of the local item to delete.")],
    s: Session = _db_dep,
):
    row = s.get(LocalWorklistItem, item_id)
    if row is None:
        raise HTTPException(404, "not found")
    before = audit.snapshot("local_item", row)
    s.delete(row)
    audit.record(s, _actor(request), "delete.local_item", "local_item", item_id, before,
                 None, _correlation(request))
    s.commit()
    local_worklist.publish_metrics()


@router.get(
    "/hl7/messages", response_model=list[Hl7MessageOut], tags=["local"],
    summary="Inbound HL7 messages",
    description="Troubleshooting log of the ORM messages the broker received "
                "(both transports), with the resulting action.",
    response_description="Recent HL7 messages, newest first.",
)
def list_hl7_messages(
    s: Session = _db_dep,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of messages."),
    offset: int = Query(default=0, ge=0, description="Number of messages to skip (paging)."),
):
    return s.scalars(
        select(Hl7Message).order_by(Hl7Message.ts.desc(), Hl7Message.id.desc())
        .offset(offset).limit(limit)
    ).all()


@router.get(
    "/mpps", response_model=list[MppsStepOut], tags=["mpps"],
    summary="Performed procedure steps (MPPS)",
    description="Steps the modalities reported, newest first. Without this the "
                "RIS never learns that an examination was performed and the order "
                "stays open.",
    response_description="MPPS entries, newest first.",
    responses=_docs(VALIDATION_422),
)
def list_mpps(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of entries."),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip (paging)."),
    status: str = Query(default="", description="Only this status (IN PROGRESS | COMPLETED | DISCONTINUED)."),
):
    return mpps.list_steps(limit=limit, offset=offset, status=status)


@router.get(
    "/mpps/stats", response_model=MppsStatsOut, tags=["mpps"],
    summary="MPPS counters",
    description="How many steps arrived, how many were reported back and what is "
                "still pending.",
    response_description="Counters for the dashboard.",
)
def mpps_stats():
    return mpps.stats()


@router.get(
    "/mpps/{step_id}", response_model=MppsStepOut, tags=["mpps"],
    summary="Read one performed procedure step",
    description="One performed procedure step by ID — the identifiers and the "
                "state the modality reported, plus whether it reached the RIS.",
    response_description="The step.",
    responses={404: {"description": "No step with this ID."}},
)
def get_mpps(
    step_id: Annotated[int, Path(description="ID of the MPPS entry.")],
):
    step = mpps.get_step(step_id)
    if step is None:
        raise HTTPException(404, "not found")
    return step


@router.post(
    "/mpps/{step_id}/forward", response_model=MppsForwardOut, tags=["mpps"],
    summary="Report one step's state again",
    description="Delivers the state message for this step to the RIS again — for "
                "a message that failed while the RIS was unreachable.",
    response_description="Whether the RIS accepted it.",
    responses={404: {"description": "No step with this ID."}, **_docs(READ_ONLY_403)},
)
def forward_mpps(
    request: Request,
    step_id: Annotated[int, Path(description="ID of the MPPS entry.")],
    s: Session = _db_dep,
):
    if mpps.get_step(step_id) is None:
        raise HTTPException(404, "not found")
    result = mpps.forward(step_id)
    audit.record(s, _actor(request), "mpps.forward", "mpps_step", step_id,
                 None, {"ok": result["ok"]}, _correlation(request))
    s.commit()
    return result


@router.post(
    "/mpps/forward-pending", response_model=MppsForwardOut, tags=["mpps"],
    summary="Report every pending step again",
    description="Retries all finished steps whose state did not reach the RIS.",
    response_description="How many were tried and how many succeeded.",
    responses=_docs(READ_ONLY_403),
)
def forward_pending_mpps(request: Request, s: Session = _db_dep):
    result = mpps.forward_pending()
    audit.record(s, _actor(request), "mpps.forward_pending", "mpps_step", None,
                 None, result, _correlation(request))
    s.commit()
    return result


@router.get(
    "/hl7/field-maps", response_model=list[Hl7FieldMapOut], tags=["local"],
    summary="List HL7 field mappings",
    description="Extra HL7 fields the broker reads into worklist attributes — for "
                "local conventions like the room in OBR-18.",
    response_description="All mappings.",
)
def list_hl7_field_maps():
    return hl7_mapping.list_maps()


@router.post(
    "/hl7/field-maps", response_model=Hl7FieldMapOut, status_code=201, tags=["local"],
    summary="Create or replace an HL7 field mapping",
    description="One mapping per HL7 location (segment, field, component). Posting "
                "the same location again replaces the target attribute.",
    response_description="The stored mapping.",
    responses=_docs(VALIDATION_422, READ_ONLY_403),
)
def create_hl7_field_map(
    request: Request,
    body: Annotated[Hl7FieldMapIn, Body(description="HL7 location and target attribute.")],
    s: Session = _db_dep,
):
    _check_hl7_map(body)
    row = hl7_mapping.upsert_map(body.segment, body.field, body.target_tag,
                                 body.component, body.enabled)
    audit.record(s, _actor(request), "hl7_field_map.create", "hl7_field_map", row["id"],
                 None, {"segment": row["segment"], "field": row["field"],
                        "target": row["target_tag"]}, _correlation(request))
    s.commit()
    return row


@router.delete(
    "/hl7/field-maps/{map_id}", status_code=204, tags=["local"],
    summary="Delete an HL7 field mapping",
    description="Removes the mapping; the field is no longer read.",
    response_description="The mapping was deleted.",
    responses=_docs(READ_ONLY_403, NOT_FOUND_404),
)
def delete_hl7_field_map(
    request: Request,
    map_id: Annotated[int, Path(description="ID of the mapping.")],
    s: Session = _db_dep,
):
    row = hl7_mapping.get_map(map_id)
    if row is None:
        raise HTTPException(404, "not found")
    hl7_mapping.delete_map(map_id)
    audit.record(s, _actor(request), "hl7_field_map.delete", "hl7_field_map", map_id,
                 {"segment": row["segment"], "target": row["target_tag"]}, None,
                 _correlation(request))
    s.commit()


@router.get(
    "/hl7/messages/{message_id}", response_model=Hl7MessageDetailOut, tags=["local"],
    summary="Read one inbound HL7 message",
    description="The log entry of one message: what was parsed, what the broker "
                "did with it and why it failed. The **raw message** (PHI) is only "
                "included when `hl7_store_raw` is switched on — otherwise "
                "reprocessing needs the sender to resend it.",
    response_description="The message log entry (raw text only when stored).",
    responses={404: {"description": "No message with this ID."}},
)
def get_hl7_message(
    message_id: Annotated[int, Path(description="ID of the message log entry.")],
    s: Session = _db_dep,
):
    row = s.get(Hl7Message, message_id)
    if row is None:
        raise HTTPException(404, "not found")
    return {
        "id": row.id,
        "ts": row.ts,
        "transport": row.transport,
        "message_type": row.message_type,
        "control_id": row.control_id,
        "order_control": row.order_control,
        "accession": row.accession,
        "action": row.action,
        "error": row.error,
        "raw": row.raw or "",
        "replayable": bool(row.raw),
    }


@router.post(
    "/hl7/messages/{message_id}/reprocess", response_model=Hl7ReprocessOut, tags=["local"],
    summary="Apply a stored HL7 message again",
    description="Parses the stored raw message again and applies it — for a message "
                "that failed because of a temporary problem (intake disabled, "
                "database busy). Requires `hl7_store_raw`; without the raw text the "
                "broker answers 409 and the sender has to resend. `dry_run=true` "
                "reports what would happen without writing.",
    response_description="What the replay did (or would do).",
    responses={404: {"description": "No message with this ID."},
               409: {"description": "The raw message was not stored (hl7_store_raw is off)."}},
)
def reprocess_hl7_message(
    request: Request,
    message_id: Annotated[int, Path(description="ID of the message log entry.")],
    dry_run: bool = Query(default=True, description="Only report; write nothing."),
    s: Session = _db_dep,
):
    row = s.get(Hl7Message, message_id)
    if row is None:
        raise HTTPException(404, "not found")
    if not row.raw:
        raise HTTPException(
            409,
            "The raw message was not stored (setting hl7_store_raw is off) — "
            "the sender has to resend it.",
        )
    parsed = hl7.parse(row.raw)
    if not parsed["accession"]:
        raise HTTPException(422, parsed["warnings"] or ["no accession number"])
    action = "cancelled" if hl7.is_cancel(parsed) else "created-or-updated"
    if dry_run:
        return {"dry_run": True, "action": action, "item_id": None, "error": ""}

    result = local_worklist.upsert_from_hl7(
        parsed, transport=f"replay:{row.transport}",
        default_station_aet=settings_service.get_str("hl7_default_station_aet"),
        default_modality=settings_service.get_str("hl7_default_modality"),
        raw=row.raw,
    )
    audit.record(s, _actor(request), f"hl7.reprocess", "hl7_message", row.id,
                 None, {"action": result["action"], "item_id": result["item_id"]},
                 _correlation(request))
    s.commit()
    return {"dry_run": False, "action": result["action"],
            "item_id": result["item_id"], "error": result.get("error", "")}


@router.post(
    "/hl7/orm", response_model=Hl7ParseOut, tags=["local"],
    summary="Apply an HL7 ORM order",
    description="Parses an ORM^O01 message and creates, updates or cancels a "
                "local worklist item. With `dry_run=true` the response only shows "
                "what the parser understood and what would happen — the check "
                "before wiring up a RIS interface.",
    response_description="The parsed fields, the planned/applied action and any warnings.",
    responses={
        422: {"description": "The message could not be parsed or carries no accession number."},
    },
)
def apply_hl7_orm(
    request: Request,
    body: Annotated[str, Body(media_type="text/plain",
                              description="The raw HL7 v2 message (ORM^O01).")],
    dry_run: bool = Query(default=True, description="Only parse and report; write nothing."),
    s: Session = _db_dep,
):
    if not settings_service.get_bool("hl7_enabled"):
        raise HTTPException(422, ["HL7 intake is disabled (setting hl7_enabled)"])
    parsed = hl7.parse(body)
    if not parsed["accession"]:
        raise HTTPException(422, parsed["warnings"] or ["no accession number"])
    # local conventions: extra fields the hospital configured
    parsed, mapped = hl7_mapping.apply_maps(parsed, body)
    if dry_run:
        action = "cancelled" if hl7.is_cancel(parsed) else "created-or-updated"
        return {"dry_run": True, "action": action, "item": None,
                **{k: parsed[k] for k in ("message_type", "control_id", "order_control", "accession")},
                "parsed": parsed, "warnings": parsed["warnings"], "mapped": mapped}

    result = local_worklist.upsert_from_hl7(
        parsed, transport="http",
        default_station_aet=settings_service.get_str("hl7_default_station_aet"),
        default_modality=settings_service.get_str("hl7_default_modality"),
        raw=body,
    )
    row = s.get(LocalWorklistItem, result["item_id"]) if result["item_id"] else None
    audit.record(s, _actor(request), f"hl7.{result['action']}", "local_item",
                 result["item_id"], None, audit.snapshot("local_item", row),
                 _correlation(request))
    s.commit()
    metrics.HL7_MESSAGES.labels(transport="http", result=result["action"]).inc()
    return {"dry_run": False, "action": result["action"],
            "item_id": result["item_id"],
            "item": _local_snapshot(row) if row is not None else None,
            **{k: parsed[k] for k in ("message_type", "control_id", "order_control", "accession")},
            "parsed": parsed, "mapped": mapped,
            "warnings": parsed["warnings"] + ([result["error"]] if result.get("error") else [])}


# ── ATNA audit trail ───────────────────────────────────────────────────


@router.get(
    "/atna/stats", response_model=AtnaStatsOut, tags=["atna"],
    summary="ATNA audit trail state",
    description="Whether the broker sends IHE ATNA audit messages, where they go "
                "and how full the delivery buffer is.",
    response_description="Audit configuration and buffer state.",
)
def atna_stats(s: Session = _db_dep):
    return atna.stats()


@router.post(
    "/atna/test", response_model=AtnaTestOut, tags=["atna"],
    summary="Send a test audit message",
    description="Delivers one audit message to the configured repository and "
                "reports whether it was accepted — the check after setting it up.",
    response_description="Delivery result of the test message.",
)
def atna_test(request: Request, s: Session = _db_dep):
    result = atna.send_test()
    audit.record(s, _actor(request), "test.atna", "setting", None,
                 None, {"ok": result["ok"]}, _correlation(request))
    s.commit()
    return result


@router.get(
    "/atna/sample", response_model=AtnaSampleOut, tags=["atna"],
    summary="Example audit message",
    description="A complete PS3.15 audit message as the broker produces it — for "
                "the team that operates the Audit Record Repository.",
    response_description="The XML of a sample Query audit message.",
)
def atna_sample(s: Session = _db_dep):
    return {"xml": atna.sample_message()}


# ── Alerting ───────────────────────────────────────────────────────────


@router.get(
    "/notify/events", response_model=list[NotifyEventOut], tags=["monitoring"],
    summary="Alerting events",
    description="The events the broker can push to a webhook. Subscribe to them "
                "with the `notify_events` setting (comma-separated codes).",
    response_description="Known event codes with severity and description.",
)
def notify_events(s: Session = _db_dep):
    return notify.events()


@router.post(
    "/notify/test", response_model=NotifyTestOut, tags=["monitoring"],
    summary="Send a test alert",
    description="Delivers a test message to the configured webhook and reports "
                "whether it was accepted — the operator's check after setting it up.",
    response_description="Delivery result of the test message.",
)
def notify_test(request: Request, s: Session = _db_dep):
    result = notify.send_test()
    audit.record(s, _actor(request), "test.notify", "setting", None,
                 None, {"ok": result["ok"]}, _correlation(request))
    s.commit()
    return result


# ── C-STORE spool ──────────────────────────────────────────────────────


@router.get(
    "/spool/stats", response_model=SpoolStatsOut, tags=["spool"],
    summary="C-STORE spool backlog",
    description="Store-and-forward queue: instances that could not be delivered "
                "are spooled and retried. Shows the backlog, the oldest entry and "
                "the capacity of the spool.",
    response_description="Backlog overview with usage and limits.",
)
def spool_stats(s: Session = _db_dep):
    return spool.stats()


@router.get(
    "/spool", response_model=list[SpoolItemOut], tags=["spool"],
    summary="Spooled C-STORE instances",
    description="Metadata of the spooled instances (the DICOM payload stays on "
                "disk). Patient identifiers are deliberately not exposed.",
    response_description="Spooled instances, newest first.",
)
def spool_items(
    s: Session = _db_dep,
    status: str | None = Query(
        default=None, description="Only entries with this status (queued | failed | dead | sent).",
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of entries."),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip (paging)."),
):
    return spool.items(status, limit, offset)


@router.post(
    "/spool/{item_id}/retry", response_model=SpoolRetryOut, tags=["spool"],
    summary="Retry one spooled instance",
    description="Puts the entry back into the queue immediately instead of "
                "waiting for the next backoff.",
    response_description="Number of requeued instances (1 on success).",
    responses={404: {"description": "No spool entry with this ID or already delivered."}},
)
def spool_retry(
    request: Request,
    item_id: Annotated[int, Path(description="ID of the spool entry to retry.")],
    s: Session = _db_dep,
):
    if not spool.retry(item_id):
        raise HTTPException(404, "not found or already delivered")
    audit.record(s, _actor(request), "retry.spool", "spool", item_id, None, None,
                 _correlation(request))
    s.commit()
    return {"requeued": 1}


@router.post(
    "/spool/retry-all", response_model=SpoolRetryOut, tags=["spool"],
    summary="Retry every failed spooled instance",
    description="Requeues all failed and dead-letter entries — the operator's "
                "action after a PACS outage.",
    response_description="Number of requeued instances.",
)
def spool_retry_all(request: Request, s: Session = _db_dep):
    count = spool.retry_all()
    audit.record(s, _actor(request), "retry_all.spool", "spool", None,
                 None, {"requeued": count}, _correlation(request))
    s.commit()
    return {"requeued": count}


@router.delete(
    "/spool/{item_id}", tags=["spool"], status_code=204,
    summary="Discard a spooled instance",
    description="Deletes the payload and the entry. **This loses the instance** "
                "— the reason is required and recorded in the change log.",
    response_description="The entry was discarded.",
    responses={404: {"description": "No spool entry with this ID."}},
)
def spool_discard(
    request: Request,
    item_id: Annotated[int, Path(description="ID of the spool entry to discard.")],
    reason: str = Query(min_length=3, max_length=200,
                        description="Why the instance is discarded (recorded in the change log)."),
    s: Session = _db_dep,
):
    if not spool.discard(item_id, reason):
        raise HTTPException(404, "not found")
    audit.record(s, _actor(request), "discard.spool", "spool", item_id,
                 {"reason": reason}, None, _correlation(request))
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
    offset: int = Query(default=0, ge=0, description="Number of items to skip (paging)."),
):
    return cache.items(source_id, limit, offset)


@router.post(
    "/cache/refresh", response_model=CacheRefreshOut, tags=["cache"],
    summary="Refresh the worklist cache now",
    description="Queries the sources again and replaces their cached snapshots — "
                "useful during an outage, when the next modality query would "
                "otherwise come too late. Answers how many items each source "
                "contributed.",
    response_description="Per source: how many items were cached and whether the source answered.",
    responses=_docs(READ_ONLY_403),
)
def refresh_cache(
    request: Request,
    source_id: int | None = Query(default=None, description="Only this source (default: all enabled)."),
    s: Session = _db_dep,
):
    from . import aggregation
    from pydicom.dataset import Dataset

    sources = aggregation.enabled_sources()
    if source_id is not None:
        if s.get(MwlSource, source_id) is None:
            raise HTTPException(404, "not found")
        sources = [src for src in sources if src.id == source_id]

    out = []
    identifier = Dataset()  # empty = every scheduled step
    for src in sources:
        answers, duration_ms, error = aggregation.query_one(src, identifier)
        if not error:
            cache.store_snapshot(src.id, answers)
        out.append({"name": src.name, "source_id": src.id, "items": len(answers),
                    "duration_ms": duration_ms, "ok": not error, "error": error})
    audit.record(s, _actor(request), "cache.refresh", "cache", source_id, None,
                 {"sources": len(out)}, _correlation(request))
    s.commit()
    return {"sources": out}


@router.delete(
    "/cache", tags=["cache"], status_code=204,
    summary="Clear the whole worklist cache",
    description="Removes every cached snapshot. The next queries go to the "
                "upstream again; an outage can no longer be bridged until then.",
    response_description="The cache was cleared.",
)
def clear_cache(request: Request, s: Session = _db_dep):
    # clearing the cache removes the outage bridge — the change log has to show it
    removed = cache.clear()
    audit.record(s, _actor(request), "cache.clear", "cache", None,
                 {"items": removed}, {"items": 0}, _correlation(request))
    s.commit()


@router.delete(
    "/cache/sources/{source_id}", tags=["cache"], status_code=204,
    summary="Clear one source's cache",
    description="Removes the cached snapshot of a single source.",
    response_description="The source's cache was cleared.",
    responses={404: {"description": "No source with this ID."}},
)
def clear_source_cache(
    request: Request,
    source_id: Annotated[int, Path(description="ID of the source whose cache is cleared.")],
    s: Session = _db_dep,
):
    if s.get(MwlSource, source_id) is None:
        raise HTTPException(404, "not found")
    removed = cache.clear(source_id)
    audit.record(s, _actor(request), "cache.clear_source", "source", source_id,
                 {"cached_items": removed}, {"cached_items": 0}, _correlation(request))
    s.commit()


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
    since: str = Query(default="", description="Only entries at or after this ISO timestamp (e.g. 2026-09-20 or 2026-09-20T08:00)."),
):
    return audit.list_entries(s, entity=entity, limit=limit, offset=offset, since=since)


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
    "/simulate/worklist", response_model=WorklistPreviewOut,
    response_model_exclude_none=True, tags=["simulation"],
    summary="Preview the merged worklist for a station",
    description="Runs the **real** C-FIND aggregation (fan-out, merge, dedupe, "
                "station rules, cache, breaker) and returns what a modality would "
                "receive — including which source contributed what. Nothing is "
                "stored as routing provenance, so looking at a case cannot change "
                "where its images go. Patient name/ID appear only when "
                "`simulate_show_phi` is switched on (PHI-free by default).",
    response_description="The merged worklist with per-source provenance and timings.",
)
def simulate_worklist(
    request: Request,
    body: WorklistPreviewIn,
    s: Session = _db_dep,
):
    identifier = _identifier_from_preview(body)
    return simulate.worklist_preview(identifier)


@router.post(
    "/sources/{source_id}/query", response_model=SourceQueryOut,
    response_model_exclude_none=True, tags=["monitoring"],
    summary="Test one source with a real C-FIND",
    description="Asks a single source directly whether it delivers worklists — "
                "the question a C-ECHO cannot answer. The answer is summarized "
                "PHI-free (accession, station, modality, date, UIDs).",
    response_description="How many answers the source returned, how long it took and a sample.",
    responses={404: {"description": "No source with this ID."}},
)
def query_source_now(
    request: Request,
    source_id: Annotated[int, Path(description="ID of the source to ask.")],
    body: SourceQueryIn | None = None,
    s: Session = _db_dep,
):
    if s.get(MwlSource, source_id) is None:
        raise HTTPException(404, "not found")
    identifier = _identifier_from_preview(body or SourceQueryIn())
    return simulate.source_query_test(source_id, identifier)


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
    "/simulate/station", response_model=StationPreviewOut, tags=["simulation"],
    summary="Simulate the per-station rules",
    description="Shows which sources a station would see and in which order they "
                "win the dedupe. Uses the same rule matching as the live C-FIND "
                "path; nothing is queried.",
    response_description="Sources with visibility and effective priority plus the matching rule.",
)
def simulate_station(
    body: StationSimulateIn,
    s: Session = _db_dep,
):
    sources = s.scalars(
        select(MwlSource).where(MwlSource.enabled.is_(True)).order_by(MwlSource.priority, MwlSource.id)
    ).all()
    from .upstream import SourceCfg

    cfgs = [
        SourceCfg(id=r.id, name=r.name, aet=r.aet, host=r.host, port=r.port,
                  calling_aet=r.calling_aet, charset=r.charset, timeout_s=r.timeout_s,
                  priority=r.priority,
                  tls=r.tls, tls_verify=r.tls_verify)
        for r in sources
    ]
    return station_rules.preview(body.station_aet, cfgs)


@router.post(
    "/simulate/stations", tags=["simulation"],
    summary="Preview several stations at once",
    description="What would each of these consoles see? Answers the same "
                "question as `/simulate/station`, but for a list of stations — "
                "the configuration check before a rollout. Empty list = every "
                "station that has a rule, plus a wildcard row.",
    response_description="One entry per station with its rule and visible sources.",
    responses=_docs(VALIDATION_422),
)
def simulate_stations(
    body: StationsSimulateIn,
    s: Session = _db_dep,
):
    from .upstream import SourceCfg

    rows = s.scalars(
        select(MwlSource).where(MwlSource.enabled.is_(True)).order_by(MwlSource.priority, MwlSource.id)
    ).all()
    cfgs = [
        SourceCfg(id=r.id, name=r.name, aet=r.aet, host=r.host, port=r.port,
                  calling_aet=r.calling_aet, charset=r.charset, timeout_s=r.timeout_s,
                  priority=r.priority, tls=r.tls, tls_verify=r.tls_verify)
        for r in rows
    ]

    wanted = [a.strip().upper() for a in body.station_aets if a.strip()]
    if not wanted:
        # every station that has a rule, plus the wildcard fallback
        rules = s.scalars(select(StationRule).order_by(StationRule.station_aet)).all()
        wanted = [r.station_aet for r in rules] or ["*"]

    return {
        "stations": [station_rules.preview(aet, cfgs) for aet in wanted],
        "source_count": len(cfgs),
    }


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
    description="One row per C-FIND the broker answered — calling AE, answering "
                "sources, duration, status and whether the cache was used. Free of "
                "patient data.",
    response_description="Query log entries, newest first.",
)
def query_logs(
    s: Session = _db_dep,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of entries."),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip."),
    calling_aet: str | None = Query(default=None, description="Only entries from this calling AE title."),
    status: str | None = Query(default=None, description="Only entries with this status (success | partial | failed)."),
    since: str = Query(default="", description="Only entries at or after this ISO timestamp (e.g. 2026-09-20 or 2026-09-20T08:00)."),
):
    q = select(QueryLog).order_by(QueryLog.ts.desc()).limit(limit).offset(offset)
    if calling_aet:
        q = q.where(QueryLog.calling_aet == calling_aet)
    if status:
        q = q.where(QueryLog.status == status)
    if since:
        q = q.where(QueryLog.ts >= _parse_since(since))
    return s.scalars(q).all()


@router.get(
    "/logs/stores", response_model=list[StoreLogOut], tags=["logs"],
    summary="C-STORE forward log",
    description="One row per forwarded instance — accession, SOP/study UID, "
                "chosen target and status. Free of patient data.",
    response_description="Store log entries, newest first.",
)
def store_logs(
    s: Session = _db_dep,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of entries."),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip."),
    status: str | None = Query(default=None, description="Only entries with this status (success | failed | unrouted)."),
    since: str = Query(default="", description="Only entries at or after this ISO timestamp (e.g. 2026-09-20 or 2026-09-20T08:00)."),
):
    q = select(StoreLog).order_by(StoreLog.ts.desc()).limit(limit).offset(offset)
    if status:
        q = q.where(StoreLog.status == status)
    if since:
        q = q.where(StoreLog.ts >= _parse_since(since))
    return s.scalars(q).all()


# ── Echo + status ──────────────────────────────────────────────────────


@router.post(
    "/sources/{source_id}/echo", response_model=EchoResult, tags=["monitoring"],
    summary="C-ECHO a source now",
    description="Associates with this source and runs a C-ECHO, using the TLS "
                "settings of the source. The result also updates the echo matrix "
                "in `GET /status`.",
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
    description="Associates with this PACS and runs a C-ECHO, using the TLS "
                "settings of the target. The result also updates the echo matrix "
                "in `GET /status`.",
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
    request: Request,
    source_id: Annotated[int, Path(description="ID of the source whose breaker is reset.")],
    s: Session = _db_dep,
):
    row = s.get(MwlSource, source_id)
    if row is None:
        raise HTTPException(404, "not found")
    before = (breaker.snapshot().get(source_id) or {}).get("state")
    breaker.reset(source_id)
    # who re-enabled a source that the broker had skipped?
    audit.record(s, _actor(request), "breaker.reset", "source", source_id,
                 {"breaker_state": before}, {"breaker_state": breaker.STATE_CLOSED},
                 _correlation(request))
    s.commit()
    log.info("breaker reset for source %s by %s", source_id, _actor(request))
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


# ── UPS-RS (DICOMweb worklist, pragmatic subset) ───────────────────────

@router.get(
    "/dicom-web/workitems", tags=["ups"],
    summary="Search work items (UPS-RS)",
    description="DICOMweb search over the work items the broker holds itself "
                "(emergencies and unscheduled examinations). Query parameters are "
                "DICOM keywords, e.g. `AccessionNumber` or `ScheduledStationAETitle`. "
                "The response uses the DICOM JSON model. Subscriptions and event "
                "reports are not implemented (see the conformance statement).",
    response_description="Matching work items as a DICOM JSON array.",
)
def ups_search(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of work items."),
):
    # the client sends DICOM keywords; the module works on the JSON tag keys
    query = {ups.QUERY_KEYS[key]: value
             for key, value in request.query_params.items() if key in ups.QUERY_KEYS}
    return ups.search(query, limit=limit)


@router.get(
    "/dicom-web/workitems/{workitem_uid}", tags=["ups"],
    summary="Retrieve one work item (UPS-RS)",
    description="One work item by its UID, in the DICOM JSON model.",
    response_description="The work item.",
    responses={404: {"description": "No work item with this UID."}},
)
def ups_retrieve(
    workitem_uid: Annotated[str, Path(description="Work item UID.")],
):
    item = ups.get_workitem(workitem_uid)
    if item is None:
        raise HTTPException(404, "not found")
    return item


@router.post(
    "/dicom-web/workitems", status_code=201, tags=["ups"],
    summary="Create a work item (UPS-RS)",
    description="Creates a local work item from a DICOM JSON body — the REST "
                "equivalent of a manually entered emergency. `AccessionNumber` is "
                "required; the created work item is returned.",
    response_description="The created work item.",
    responses=_docs(VALIDATION_422, READ_ONLY_403),
)
def ups_create(
    request: Request,
    body: Annotated[dict, Body(description="Work item in the DICOM JSON model.")],
    s: Session = _db_dep,
):
    try:
        item = ups.create_workitem(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    audit.record(s, _actor(request), "ups.create", "local_item", None, None,
                 {"accession": item.get("00080050", {}).get("Value", [""])[0]},
                 _correlation(request))
    s.commit()
    return item


@router.put(
    "/dicom-web/workitems/{workitem_uid}/state", tags=["ups"],
    summary="Change the state of a work item (UPS-RS)",
    description="Sets the procedure step state (SCHEDULED, IN PROGRESS, COMPLETED, "
                "CANCELED). COMPLETED and CANCELED take the work item out of the "
                "worklist, like a finished MPPS step.",
    response_description="The work item after the change.",
    responses={404: {"description": "No work item with this UID."},
               **_docs(VALIDATION_422, READ_ONLY_403)},
)
def ups_set_state(
    request: Request,
    workitem_uid: Annotated[str, Path(description="Work item UID.")],
    body: Annotated[dict, Body(description="{\"state\": \"IN PROGRESS\"} or a DICOM JSON state value.")],
    s: Session = _db_dep,
):
    state = str(body.get("state") or ups._read_value(body, "00404041") or "")
    try:
        item = ups.set_state(workitem_uid, state)
    except LookupError:
        raise HTTPException(404, "not found")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    audit.record(s, _actor(request), "ups.state", "local_item", None, None,
                 {"state": state}, _correlation(request))
    s.commit()
    return item


@router.get(
    "/stats/overview", response_model=StatsOut, tags=["monitoring"],
    summary="Reporting overview",
    description="How busy the broker was and where it hurt: queries, answers, "
                "forwarded instances, failures, MPPS and spool state — broken down "
                "by source, modality or station, plus a daily series. Everything is "
                "derived from the existing logs and stays PHI-free.",
    response_description="Totals, breakdown and daily series for the period.",
    responses=_docs(VALIDATION_422),
)
def stats_overview(
    days: int = Query(default=7, ge=1, le=366, description="Length of the period in days."),
    group_by: str = Query(default="source", pattern="^(source|modality|station)$",
                          description="Breakdown dimension: source, modality or station."),
):
    return stats.overview(days=days, group_by=group_by)


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

    from . import __version__

    return {
        # which build is this? (the operator asked exactly that)
        "version": __version__,
        "started_at": _STARTED_AT.isoformat(),
        "uptime_s": int((datetime.now(timezone.utc) - _STARTED_AT).total_seconds()),
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
