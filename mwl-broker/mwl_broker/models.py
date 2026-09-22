"""SQLAlchemy models — schema documented in ../project.md.

PHI policy: PatientName is never persisted here. PatientID only in
seen_items (needed for store routing) and subject to retention purge.
"""
from datetime import datetime, timezone

from sqlalchemy import Text, JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
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
    priority: Mapped[int] = mapped_column(Integer, default=100)
    # May this source be answered from the cache when it is unreachable?
    cache_stale_on_error: Mapped[bool] = mapped_column(Boolean, default=True)
    # Optional background refresh of the cached snapshot (0 = off, seconds).
    cache_refresh_s: Mapped[int] = mapped_column(Integer, default=0)  # lower = queried first
    # DICOM TLS for this node (off = the LAN/VPN default)
    tls: Mapped[bool] = mapped_column(Boolean, default=False)
    tls_verify: Mapped[bool] = mapped_column(Boolean, default=True)
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
    tls: Mapped[bool] = mapped_column(Boolean, default=False)
    tls_verify: Mapped[bool] = mapped_column(Boolean, default=True)
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


class TransformRule(Base):
    """DICOM attribute modifications applied before forwarding a C-STORE.

    Scope: `source_id` / `target_id` may be NULL (= any). All applicable,
    enabled rules are applied in priority order. `operations` is a JSON list:

        [{"op": "set",    "tag": "AccessionNumber", "value": "KH-1"},
         {"op": "prefix", "tag": "PatientID",       "value": "KH_"},
         {"op": "suffix", "tag": "StudyDescription","value": " (KH)"},
         {"op": "replace","tag": "InstitutionName", "pattern": "^ALT", "value": "KH"},
         {"op": "copy",   "tag": "StudyDescription","from_tag": "RequestedProcedureDescription"},
         {"op": "remove", "tag": "PatientAddress"}]
    """

    __tablename__ = "transform_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("mwl_source.id"), nullable=True, index=True
    )
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("pacs_target.id"), nullable=True, index=True
    )
    operations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SourceBreaker(Base):
    """Circuit-breaker state for one upstream source.

    Persisted so a broker restart does not forget that a source is down.
    A missing row means "closed" (healthy) — rows are created on the first
    failure and removed when the source is deleted.
    """

    __tablename__ = "source_breaker"

    source_id: Mapped[int] = mapped_column(
        ForeignKey("mwl_source.id"), primary_key=True
    )
    state: Mapped[str] = mapped_column(String(16), default="closed")  # closed|half_open|open
    failures: Mapped[int] = mapped_column(Integer, default=0)
    open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(String(512), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class WorklistCache(Base):
    """Cached worklist answers per source — the outage bridge.

    The upstream RIS stays the source of truth: a successful query *replaces*
    the whole snapshot for that source, so completed orders disappear
    immediately (they are simply no longer in the answer). The cache is only
    served when the upstream fails, and only for a bounded window.

    `payload` holds the answer dataset as DICOM JSON — **this contains PHI**
    (that is the point of a worklist). It is never logged and never exposed
    through the API; see docs/roadmap-worklist-broker.md for the deletion
    concept (TTL + purge + explicit clear).
    """

    __tablename__ = "worklist_cache"
    __table_args__ = (UniqueConstraint("source_id", "dedupe_key", name="uq_cache_source_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("mwl_source.id"), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(512))
    accession: Mapped[str] = mapped_column(String(64), default="")
    study_uid: Mapped[str] = mapped_column(String(128), default="")
    modality: Mapped[str] = mapped_column(String(16), default="")
    station_aet: Mapped[str] = mapped_column(String(16), default="")
    sps_status: Mapped[str] = mapped_column(String(16), default="")
    payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class LocalWorklistItem(Base):
    """A worklist entry that exists only in the broker.

    Emergencies and unscheduled examinations exist in no RIS, so the broker can
    hold them itself — created in the UI or pushed as an HL7 ORM message. They
    are merged into every C-FIND with the highest priority and attributed to the
    pseudo source `local`, which makes them routable like any other worklist
    source.

    Unlike the cache this table is *actively maintained* data, so the operator
    API returns the patient name (the editor needs it). The broker's own logs
    stay PHI-free.
    """

    __tablename__ = "local_worklist_item"
    __table_args__ = (UniqueConstraint("accession", "sps_id", name="uq_local_item_step"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    accession: Mapped[str] = mapped_column(String(64), index=True)
    sps_id: Mapped[str] = mapped_column(String(64), default="1")
    # values a local HL7 field mapping added (DICOM keyword → value); they are
    # merged into the C-FIND answer like any other attribute
    extra_attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    patient_id: Mapped[str] = mapped_column(String(64), default="")
    patient_name: Mapped[str] = mapped_column(String(128), default="")
    birth_date: Mapped[str] = mapped_column(String(16), default="")
    sex: Mapped[str] = mapped_column(String(4), default="")
    modality: Mapped[str] = mapped_column(String(16), default="")
    station_aet: Mapped[str] = mapped_column(String(16), default="")
    procedure_description: Mapped[str] = mapped_column(String(128), default="")
    scheduled_date: Mapped[str] = mapped_column(String(16), default="")
    scheduled_time: Mapped[str] = mapped_column(String(16), default="")
    study_uid: Mapped[str] = mapped_column(String(128), default="")
    sps_status: Mapped[str] = mapped_column(String(16), default="SCHEDULED")
    # optional expiry: an emergency entry should not live forever
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    origin: Mapped[str] = mapped_column(String(16), default="manual")  # manual | hl7
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Hl7Message(Base):
    """Inbound HL7 message log — troubleshooting for the interface."""

    __tablename__ = "hl7_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    transport: Mapped[str] = mapped_column(String(8), default="http")  # http | mllp
    message_type: Mapped[str] = mapped_column(String(16), default="")
    control_id: Mapped[str] = mapped_column(String(64), default="")
    order_control: Mapped[str] = mapped_column(String(8), default="")
    accession: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(32), default="")
    error: Mapped[str] = mapped_column(String(256), default="")
    # The raw message is PHI (it carries the patient name). It is only kept when
    # the operator switches `hl7_store_raw` on — otherwise reprocessing needs the
    # RIS to resend the message.
    raw: Mapped[str] = mapped_column(Text, default="")


class StationRule(Base):
    """Per-station worklist filter and source priority.

    A console should see *its* worklist: the rule restricts which sources are
    visible to a station (`mode: allow|deny` + `source_ids`) and can override the
    merge order for that station (`source_priority`), so the emergency RIS wins
    the dedupe for the CT but the routine RIS for the X-ray room.

    `station_aet` is matched against `ScheduledStationAETitle` of the incoming
    C-FIND; `*` is the fallback rule. Filtering happens **after** the merge, so
    deduplication stays unaffected by station rules.
    """

    __tablename__ = "station_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    station_aet: Mapped[str] = mapped_column(String(16), default="*", index=True)
    # allow: only the listed sources are visible; deny: the listed ones are hidden
    mode: Mapped[str] = mapped_column(String(8), default="deny")
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    source_priority: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class StoreSpool(Base):
    """Spooled C-STORE instances that could not be forwarded yet.

    Store-and-forward: the payload is written to disk (`payload_path`) and the
    row carries the metadata, so the database index stays small and the spool
    can live on its own volume with its own size budget. The file is deleted
    once the instance reached its target; the row stays for
    `spool_retention_s` as a duplicate guard (the same SOPInstanceUID must not
    be forwarded twice).

    `target_id` is a plain integer (no FK): an instance must never be dropped
    because somebody deleted a target — a missing target turns the entry into a
    dead letter, which the operator sees and can retry or discard.

    `claimed_by`/`lease_until` are the high-availability guard: with a second
    broker instance on the same database, a worker **claims** an entry for a
    bounded lease before forwarding it, so two instances cannot deliver the same
    instance twice. An expired lease means the claiming instance died — the entry
    becomes available again (at-least-once, never silently lost).
    """

    __tablename__ = "store_spool"

    id: Mapped[int] = mapped_column(primary_key=True)
    sop_instance_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    study_uid: Mapped[str] = mapped_column(String(128), default="", index=True)
    accession: Mapped[str] = mapped_column(String(64), default="", index=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_name: Mapped[str] = mapped_column(String(64), default="")
    payload_path: Mapped[str] = mapped_column(String(512), default="")
    payload_bytes: Mapped[int] = mapped_column(Integer, default=0)
    # queued | sent | failed | dead
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # which broker instance holds this entry, and until when (empty/None = free)
    claimed_by: Mapped[str] = mapped_column(String(64), default="", index=True)
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_error: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BrokerInstance(Base):
    """One running broker process — the heartbeat that makes HA visible.

    Several instances may share the database and the spool volume (see
    `docs/ha.md`). Each writes its own row; the operator sees in the UI which
    instances are alive, and the health checks warn when a second one is active
    while the deployment may not be prepared for it (spool volume not shared,
    modalities not behind a VIP).

    Rows are not patient data: instance name, version, host, pid, timestamps.
    """

    __tablename__ = "broker_instance"

    instance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow,
                                                index=True)
    version: Mapped[str] = mapped_column(String(32), default="")
    hostname: Mapped[str] = mapped_column(String(128), default="")
    pid: Mapped[int] = mapped_column(Integer, default=0)


class ConfigAudit(Base):
    """Server-side change log for every configuration mutation.

    `before_json`/`after_json` hold the serialized row; they are the basis for
    the diff view and for the rollback endpoint. Configuration only — never
    patient data.
    """

    __tablename__ = "config_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(128), default="api")
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), default="")


class BrokerSetting(Base):
    """Runtime setting overriding the ENV default (ENV stays the fallback).

    Known keys and validation live in settings_service.py.
    """

    __tablename__ = "broker_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


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
    status: Mapped[str] = mapped_column(String(16), default="success")
    # sources that had to be answered from the worklist cache (JSON list)
    served_stale: Mapped[list | None] = mapped_column(JSON, nullable=True)  # success|partial|failed


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
    # Names of the transform rules applied to this instance (audit trail).
    applied_transforms: Mapped[list] = mapped_column(JSON, default=list)


class MppsStep(Base):
    """A performed procedure step reported by a modality (MPPS).

    The broker accepts N-CREATE ("IN PROGRESS") and N-SET ("COMPLETED" /
    "DISCONTINUED"), keeps the identifiers the RIS needs for its own status
    update and — when switched on — forwards the state back as HL7. Without this
    the order would stay open in the RIS, because the RIS never learns that the
    examination happened.

    PHI: the table holds the patient ID only (like `seen_items`), never the name.
    """

    __tablename__ = "mpps_step"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    sop_instance_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="IN PROGRESS", index=True)
    accession: Mapped[str] = mapped_column(String(64), default="")
    patient_id: Mapped[str] = mapped_column(String(64), default="")
    sps_id: Mapped[str] = mapped_column(String(64), default="")
    station_aet: Mapped[str] = mapped_column(String(16), default="")
    modality: Mapped[str] = mapped_column(String(16), default="")
    study_uid: Mapped[str] = mapped_column(String(128), default="")
    performed_procedure_step_id: Mapped[str] = mapped_column(String(64), default="")
    # when the modality reported the transitions (not when the broker stored them)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # forwarding the state back to the RIS
    forwarded: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    forward_error: Mapped[str] = mapped_column(String(256), default="")
    forward_attempts: Mapped[int] = mapped_column(Integer, default=0)
    forwarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MergeRule(Base):
    """Which source wins for one DICOM attribute.

    The default merge takes the whole item from the highest-priority source that
    knows the case. A rule like `PatientName ← his-feed,ris-a` overrides just
    that field: demographics from the HIS feed, everything else from the RIS.
    """

    __tablename__ = "merge_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    tag: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sources: Mapped[str] = mapped_column(String(512), default="")   # comma separated, in order
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Hl7FieldMap(Base):
    """Read an extra value out of the ORM message into a worklist attribute.

    Hospitals put local information in non-standard places (room in OBR-18,
    contrast agent in a ZSD segment). A mapping names the HL7 location and the
    DICOM attribute it fills — no code change for a local convention.
    """

    __tablename__ = "hl7_field_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    segment: Mapped[str] = mapped_column(String(8), default="")     # ORC, OBR, ZDS, PID …
    field: Mapped[int] = mapped_column(Integer, default=1)          # HL7 field number (1-based)
    component: Mapped[int] = mapped_column(Integer, default=0)      # component inside the field
    target_tag: Mapped[str] = mapped_column(String(64), default="")  # DICOM keyword
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PatientMerge(Base):
    """`old_patient_id` is now `new_patient_id` (IHE Patient Information Reconciliation).

    Announced by the RIS as HL7 ADT (`A40` merge, `A24` link) or entered by an
    operator. The worklist answer and the routing provenance both use the
    resolved ID, so a merge changes what the modality sees *and* where images are
    routed.

    `kind` separates the two: a **merge** (`A40`) retires the old identifier, so
    the worklist answer is rewritten to the current ID. A **link** (`A24`) only
    records that the two records are the same person — both identifiers stay
    valid, and an answer that came back under the old ID is served unchanged.
    """

    __tablename__ = "patient_merge"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    old_patient_id: Mapped[str] = mapped_column(String(64), index=True)
    new_patient_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(256), default="")
    actor: Mapped[str] = mapped_column(String(64), default="api")
    origin: Mapped[str] = mapped_column(String(16), default="manual")   # manual | adt
    kind: Mapped[str] = mapped_column(String(16), default="merge", index=True)  # merge | link
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
