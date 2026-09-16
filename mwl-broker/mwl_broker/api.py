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


def _crud(router: APIRouter, path: str, model, in_schema, out_schema):
    """Register list/create/get/update/delete for a model with `name`."""

    @router.get(path, response_model=list[out_schema], name=f"list_{path[1:]}")
    def _list(s: Session = _db_dep):
        return s.scalars(select(model).order_by(model.id)).all()

    @router.post(path, response_model=out_schema, status_code=201, name=f"create_{path[1:]}")
    def _create(body: in_schema, s: Session = _db_dep):
        if s.scalar(select(model).where(model.name == body.name)):
            raise HTTPException(409, f"{body.name} already exists")
        row = model(**body.model_dump())
        s.add(row)
        s.commit()
        s.refresh(row)
        return row

    @router.put(path + "/{row_id}", response_model=out_schema, name=f"update_{path[1:]}")
    def _update(row_id: int, body: in_schema, s: Session = _db_dep):
        row = s.get(model, row_id)
        if row is None:
            raise HTTPException(404, "not found")
        for k, v in body.model_dump().items():
            setattr(row, k, v)
        s.commit()
        s.refresh(row)
        return row

    @router.delete(path + "/{row_id}", status_code=204, name=f"delete_{path[1:]}")
    def _delete(row_id: int, s: Session = _db_dep):
        row = s.get(model, row_id)
        if row is None:
            raise HTTPException(404, "not found")
        s.delete(row)
        s.commit()


_crud(router, "/sources", MwlSource, SourceIn, SourceOut)
_crud(router, "/targets", PacsTarget, TargetIn, TargetOut)


# ── Routing rules ──────────────────────────────────────────────────────


@router.get("/rules", response_model=list[RuleOut])
def list_rules(s: Session = _db_dep):
    return s.scalars(select(RoutingRule).order_by(RoutingRule.priority, RoutingRule.id)).all()


@router.post("/rules", response_model=RuleOut, status_code=201)
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


@router.put("/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, body: RuleIn, s: Session = _db_dep):
    row = s.get(RoutingRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    s.commit()
    s.refresh(row)
    return row


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, s: Session = _db_dep):
    row = s.get(RoutingRule, rule_id)
    if row is None:
        raise HTTPException(404, "not found")
    s.delete(row)
    s.commit()


# ── Logs ───────────────────────────────────────────────────────────────


@router.get("/logs/queries", response_model=list[QueryLogOut])
def query_logs(
    s: Session = _db_dep,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    calling_aet: str | None = None,
    status: str | None = None,
):
    q = select(QueryLog).order_by(QueryLog.ts.desc()).limit(limit).offset(offset)
    if calling_aet:
        q = q.where(QueryLog.calling_aet == calling_aet)
    if status:
        q = q.where(QueryLog.status == status)
    return s.scalars(q).all()


@router.get("/logs/stores", response_model=list[StoreLogOut])
def store_logs(
    s: Session = _db_dep,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    status: str | None = None,
):
    q = select(StoreLog).order_by(StoreLog.ts.desc()).limit(limit).offset(offset)
    if status:
        q = q.where(StoreLog.status == status)
    return s.scalars(q).all()


# ── Echo + status ──────────────────────────────────────────────────────


@router.post("/sources/{source_id}/echo", response_model=EchoResult)
def echo_source(source_id: int, s: Session = _db_dep):
    row = s.get(MwlSource, source_id)
    if row is None:
        raise HTTPException(404, "not found")
    return echo_one("source", row)


@router.post("/targets/{target_id}/echo", response_model=EchoResult)
def echo_target(target_id: int, s: Session = _db_dep):
    row = s.get(PacsTarget, target_id)
    if row is None:
        raise HTTPException(404, "not found")
    return echo_one("target", row)


@router.get("/status", response_model=StatusOut)
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
