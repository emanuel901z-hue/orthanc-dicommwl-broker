"""DB engine/session factory — lazy so tests can override DATABASE_URL
via BROKER_DATABASE_URL before first use."""
import logging

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base, MwlSource, PacsTarget, RoutingRule

log = logging.getLogger("mwl_broker.db")

_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def get_session() -> Session:
    return session_factory()()


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def reset_for_tests() -> None:
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def seed_from_json(payload: list[dict]) -> None:
    """Idempotent upsert of sources/targets/rules from a JSON seed list.

    Items: {"kind": "source"|"target", ...model fields...}
    Rules:  {"kind": "rule", "source": "<name>", "target": "<name>", ...}
    """
    kind_model = {"source": MwlSource, "target": PacsTarget}
    with get_session() as s:
        for item in payload:
            item = dict(item)
            kind = item.pop("kind", "")
            if kind == "rule":
                _seed_rule(s, item)
                continue
            model = kind_model.get(kind)
            if model is None:
                continue
            existing = s.scalar(select(model).where(model.name == item["name"]))
            if existing is None:
                s.add(model(**item))
            else:
                for k, v in item.items():
                    setattr(existing, k, v)
        s.commit()


def _seed_rule(s, item: dict) -> None:
    """Upsert a routing rule referenced by source/target *names*."""
    src = s.scalar(select(MwlSource).where(MwlSource.name == item["source"]))
    tgt = s.scalar(select(PacsTarget).where(PacsTarget.name == item["target"]))
    if src is None or tgt is None:
        log.warning("seed rule skipped: unknown source/target %s", item)
        return
    fields = {"priority": item.get("priority", 100),
              "enabled": item.get("enabled", True)}
    existing = s.scalar(
        select(RoutingRule).where(
            RoutingRule.source_id == src.id, RoutingRule.target_id == tgt.id
        )
    )
    if existing is None:
        s.add(RoutingRule(source_id=src.id, target_id=tgt.id, **fields))
    else:
        for k, v in fields.items():
            setattr(existing, k, v)


def check_db() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
