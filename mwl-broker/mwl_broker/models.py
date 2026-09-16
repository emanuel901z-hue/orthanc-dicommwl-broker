"""SQLAlchemy models — schema documented in ../project.md.

PHI policy: PatientName is never persisted here. PatientID only in
seen_items (needed for store routing) and subject to retention purge.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class MwlSource(Base):
    """Upstream MWL provider (RIS/KIS) the broker queries via C-FIND SCU."""

    __tablename__ = "mwl_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    aet: Mapped[str] = mapped_column(String(16))  # called AET of the source
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    calling_aet: Mapped[str] = mapped_column(String(16), default="MWLBROKER")
    charset: Mapped[str] = mapped_column(String(32), default="ISO_IR 100")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout_s: Mapped[int] = mapped_column(Integer, default=10)
    priority: Mapped[int] = mapped_column(Integer, default=100)  # lower = queried first
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PacsTarget(Base):
    """DICOM node receiving forwarded C-STOREs (PACS, Orthanc, ...)."""

    __tablename__ = "pacs_target"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    aet: Mapped[str] = mapped_column(String(16))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    calling_aet: Mapped[str] = mapped_column(String(16), default="MWLBROKER")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RoutingRule(Base):
    """Maps a worklist source to a PACS target. First enabled rule wins
    (ordered by priority)."""

    __tablename__ = "routing_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("mwl_source.id"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("pacs_target.id"))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SeenItem(Base):
    """Worklist items that flowed through a C-FIND answer — used to map
    incoming C-STOREs back to their originating source."""

    __tablename__ = "seen_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    accession: Mapped[str] = mapped_column(String(64), index=True, default="")
    sps_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    study_uid: Mapped[str] = mapped_column(String(128), index=True, default="")
    patient_id: Mapped[str] = mapped_column(String(64), default="")
    source_id: Mapped[int] = mapped_column(ForeignKey("mwl_source.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class QueryLog(Base):
    """One row per incoming C-FIND. No PHI — query keys are filtered."""

    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    calling_aet: Mapped[str] = mapped_column(String(16), index=True)
    query_keys: Mapped[dict] = mapped_column(JSON, default=dict)
    answers: Mapped[int] = mapped_column(Integer, default=0)
    per_source: Mapped[dict] = mapped_column(JSON, default=dict)  # {source_name: count|"error"}
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="success")  # success|partial|failed


class StoreLog(Base):
    """One row per incoming C-STORE forward attempt."""

    __tablename__ = "store_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    calling_aet: Mapped[str] = mapped_column(String(16), default="")
    sop_instance_uid: Mapped[str] = mapped_column(String(128), default="")
    study_uid: Mapped[str] = mapped_column(String(128), default="", index=True)
    accession: Mapped[str] = mapped_column(String(64), default="", index=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="success")  # success|failed|unrouted
    error: Mapped[str] = mapped_column(String(512), default="")
