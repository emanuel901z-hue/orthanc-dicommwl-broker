"""REST API: CRUD for sources/targets/rules, logs, status.

All endpoints are sync `def` — they run in the FastAPI threadpool, which
keeps them consistent with the synchronous DIMSE handlers.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
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
    EchoResult,
    QueryLogOut,
    RuleIn,
    RuleOut,
    SourceIn,
    SourceOut,
    StatusOut,
    StoreLogOut,
    TargetIn,
    TargetOut,
)

router = APIRouter(prefix="/api/v1")

_scp = None  # set by main.py for /status


def bind_scp(scp) -> None:
    global _scp
    _scp = scp


def _db() -> Session:
    s = get_session()
    try:
        yield s
    finally:
        s.close()


_db_dep = Depends(_db)


def _crud(router: APIRouter, path: str, model, in_schema, out_schema, kind: str):
    """Register list/create/get/update/delete for a model with `name`."""

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
    def _create(body: in_schema, s: Session = _db_dep):
        if s.scalar(select(model).where(model.name == body.name)):
            raise HTTPException(409, f"{body.name} already exists")
        row = model(**body.model_dump())
        s.add(row)
        s.commit()
        s.refresh(row)
        return row

    @router.put(
        path + "/{row_id}", response_model=out_schema, name=f"update_{path[1:]}",
        tags=[f"{path[1:]}"], summary=f"Update a {kind}",
        response_description=f"The updated {kind}.",
        responses={404: {"description": f"No {kind} with this ID."}},
    )
    def _update(row_id: int, body: in_schema, s: Session = _db_dep):
        row = s.get(model, row_id)
        if row is None:
            raise HTTPException(404, "not found")
        for k, v in body.model_dump().items():
            setattr(row, k, v)
        s.commit()
        s.refresh(row)
        return row

    @router.delete(
        path + "/{row_id}", status_code=204, name=f"delete_{path[1:]}",
        tags=[f"{path[1:]}"], summary=f"Delete a {kind}",
        responses={404: {"description": f"No {kind} with this ID."}},
    )
    def _delete(row_id: int, s: Session = _db_dep):
        row = s.get(model, row_id)
        if row is None:
            raise HTTPException(404, "not found")
        s.delete(row)
        s.commit()


_crud(router, "/sources", MwlSource, SourceIn, SourceOut, "source")
_crud(router, "/targets", PacsTarget, TargetIn, TargetOut, "target")


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
def create_rule(body: RuleIn, s: Session = _db_dep):
    for mid, label in ((body.source_id, "source"), (body.target_id, "target")):
        model = MwlSource if label == "source" else PacsTarget
        if s.get(model, mid) is None:
            raise HTTPException(404, f"{label} {mid} not found")
    row = RoutingRule(**body.model_dump())
    s.add(row)
    s.commit()
    s.refresh(row)
    return row


@router.put(
    "/rules/{rule_id}", response_model=RuleOut, tags=["rules"],
    summary="Update a routing rule",
    response_description="The updated rule.",
    responses={404: {"description": "No rule with this ID."}},
)
def update_rule(rule_id: int, body: RuleIn, s: Session = _db_dep):
    row = s.get(RoutingRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    s.commit()
    s.refresh(row)
    return row


@router.delete(
    "/rules/{rule_id}", status_code=204, tags=["rules"],
    summary="Delete a routing rule",
    responses={404: {"description": "No rule with this ID."}},
)
def delete_rule(rule_id: int, s: Session = _db_dep):
    row = s.get(RoutingRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    s.delete(row)
    s.commit()


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
def echo_source(source_id: int, s: Session = _db_dep):
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
def echo_target(target_id: int, s: Session = _db_dep):
    row = s.get(PacsTarget, target_id)
    if row is None:
        raise HTTPException(404, "not found")
    return echo_one("target", row)


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

    def with_echo(model_rows, kind):
        by_id = {e["id"]: e for e in snap[kind]}
        out = []
        for r in model_rows:
            e = by_id.get(r.id) or {
                "kind": kind, "id": r.id, "name": r.name,
                "ok": False, "rtt_ms": None, "last_check": None, "error": "never checked",
            }
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
