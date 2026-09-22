"""Locally maintained worklist items — emergencies and unscheduled exams.

An item created here (in the UI or from an HL7 ORM message) is merged into every
C-FIND answer with the **highest priority**, so a locally scheduled emergency
wins the dedupe against the RIS. Provenance is the pseudo source `local`: it is
never queried (it stays disabled) but it can be used in routing rules, which is
what lets an emergency land in a different PACS.

Matching honours the modality's query keys (patient, accession, modality,
station, date), so a CT console does not suddenly see the X-ray room's items.
"""
import logging
from datetime import datetime, timedelta, timezone

from pydicom.dataset import Dataset
from sqlalchemy import select

from . import metrics, settings_service
from .db import session_factory
from .models import Hl7Message, LocalWorklistItem, MwlSource
from .upstream import SourceCfg

log = logging.getLogger("mwl_broker.local_worklist")

LOCAL_SOURCE_NAME = "local"
LOCAL_SOURCE_AET = "MWL_LOCAL"

MATCH_KEYS = ("PatientID", "AccessionNumber")
SPS_MATCH_KEYS = ("Modality", "ScheduledStationAETitle", "ScheduledProcedureStepStartDate")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def local_source_id() -> int:
    """The pseudo source local items are attributed to (created on demand)."""
    with session_factory()() as s:
        row = s.scalars(select(MwlSource).where(MwlSource.name == LOCAL_SOURCE_NAME)).first()
        if row is None:
            row = MwlSource(name=LOCAL_SOURCE_NAME, aet=LOCAL_SOURCE_AET, host="localhost",
                            port=11113, calling_aet="MWLBROKER", charset="ISO_IR 100",
                            enabled=False, priority=0)
            s.add(row)
            s.commit()
            log.info("created the '%s' pseudo source for local worklist items", LOCAL_SOURCE_NAME)
        return row.id


def local_source_cfg() -> SourceCfg:
    """The pseudo source as a config object (never actually queried)."""
    return SourceCfg(id=local_source_id(), name=LOCAL_SOURCE_NAME, aet=LOCAL_SOURCE_AET,
                     host="localhost", port=11113, calling_aet="MWLBROKER",
                     charset="ISO_IR 100", timeout_s=1, priority=-1)


def local_priority() -> int:
    """Merge priority of local items (default: before every upstream source)."""
    return settings_service.get_int("local_priority")


# ── DICOM view ─────────────────────────────────────────────────────────


def to_dataset(item: LocalWorklistItem, charset: str = "ISO_IR 100") -> Dataset:
    """Render one local item as a worklist answer."""
    ds = Dataset()
    ds.SpecificCharacterSet = charset
    ds.PatientID = item.patient_id
    ds.PatientName = item.patient_name or ""
    if item.birth_date:
        ds.PatientBirthDate = item.birth_date.replace("-", "")
    if item.sex:
        ds.PatientSex = item.sex
    ds.AccessionNumber = item.accession
    if item.study_uid:
        ds.StudyInstanceUID = item.study_uid
    ds.RequestedProcedureID = item.sps_id
    ds.RequestedProcedureDescription = item.procedure_description or ""

    sps = Dataset()
    sps.ScheduledProcedureStepID = item.sps_id
    sps.ScheduledStationAETitle = item.station_aet or ""
    sps.ScheduledProcedureStepStartDate = (item.scheduled_date or "").replace("-", "")
    sps.ScheduledProcedureStepStartTime = (item.scheduled_time or "").replace(":", "")
    sps.Modality = item.modality or ""
    sps.ScheduledProcedureStepDescription = item.procedure_description or ""
    sps.ScheduledProcedureStepStatus = item.sps_status or "SCHEDULED"
    # fields a local HL7 mapping added belong in the answer like any other
    for tag, value in (getattr(item, "extra_attributes", None) or {}).items():
        try:
            setattr(ds, tag, value)
        except Exception:  # an unknown keyword must not break the answer
            log.warning("local item %s: cannot set mapped attribute %s", item.id, tag)
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


def _matches(query: Dataset, item: LocalWorklistItem) -> bool:
    """Honour the query keys a modality sent (empty key = match everything)."""
    ds = to_dataset(item)
    sps = ds.ScheduledProcedureStepSequence[0]
    for key in MATCH_KEYS:
        want = str(query.get(key, "") or "").strip()
        if want and want.rstrip("*").lower() not in str(ds.get(key, "") or "").lower():
            return False
    for key in SPS_MATCH_KEYS:
        want = str(query.get(key, "") or "").strip()
        if not want:
            sps_seq = query.get("ScheduledProcedureStepSequence") or []
            if sps_seq:
                want = str(sps_seq[0].get(key, "") or "").strip()
        if want and want.rstrip("*").lower() not in str(sps.get(key, "") or "").lower():
            return False
    return True


def active_items(identifier: Dataset) -> list[LocalWorklistItem]:
    """Enabled, unexpired local items matching the incoming query."""
    now = _now()
    with session_factory()() as s:
        rows = s.scalars(
            select(LocalWorklistItem)
            .where(LocalWorklistItem.enabled.is_(True))
            .order_by(LocalWorklistItem.id)
        ).all()
        out = []
        for row in rows:
            expires = _as_aware(row.valid_until)
            if expires is not None and expires < now:
                continue
            if _matches(identifier, row):
                out.append(row)
        return out


def answers_for(identifier: Dataset, charset: str = "ISO_IR 100") -> tuple[SourceCfg, list[Dataset]] | None:
    """The local contribution to a C-FIND (None when there is nothing local)."""
    items = active_items(identifier)
    if not items:
        return None
    return local_source_cfg(), [to_dataset(item, charset) for item in items]


def publish_metrics() -> None:
    with session_factory()() as s:
        count = len(s.scalars(
            select(LocalWorklistItem).where(LocalWorklistItem.enabled.is_(True))
        ).all())
    metrics.LOCAL_ITEMS.set(count)


# ── maintenance ────────────────────────────────────────────────────────


def purge_expired() -> int:
    """Remove items whose validity window has passed."""
    now = _now()
    removed = 0
    with session_factory()() as s:
        for row in s.scalars(select(LocalWorklistItem)).all():
            expires = _as_aware(row.valid_until)
            if expires is not None and expires < now:
                s.delete(row)
                removed += 1
        if removed:
            s.commit()
    if removed:
        log.info("local worklist: purged %d expired item(s)", removed)
        publish_metrics()
    return removed


def update_demographics(patient_id: str, *, patient_name: str = "",
                        birth_date: str = "", sex: str = "") -> int:
    """Apply a demographics update (ADT A08) to the items of one patient.

    Only the fields the message actually carries are overwritten — an A08 that
    changes the name must not blank the birth date. Returns how many items
    changed. The patient ID itself is never rewritten here: that is a merge
    (`merges.merge`), and `adt` resolves a retired ID before calling.

    PHI: this is the table that legitimately holds the name (the modality shows
    it), so nothing is logged from here.
    """
    pid = (patient_id or "").strip()
    if not pid:
        return 0
    changed = 0
    with session_factory()() as s:
        for item in s.scalars(
            select(LocalWorklistItem).where(LocalWorklistItem.patient_id == pid)
        ).all():
            touched = False
            for field, value in (("patient_name", patient_name),
                                 ("birth_date", birth_date), ("sex", sex)):
                if value and getattr(item, field) != value:
                    setattr(item, field, value)
                    touched = True
            if touched:
                changed += 1
        if changed:
            s.commit()
    if changed:
        log.info("ADT A08: demographics of %d local item(s) updated", changed)
    return changed


def log_hl7(transport: str, parsed: dict, action: str, error: str = "",
            raw: str = "") -> None:
    """Record an inbound message (both transports) for troubleshooting.

    The raw message is PHI, so it is only kept when `hl7_store_raw` is on — then
    the operator can inspect and replay it (retention still applies).
    """
    from . import settings_service

    keep_raw = settings_service.get_bool("hl7_store_raw")
    try:
        with session_factory()() as s:
            s.add(Hl7Message(
                transport=transport, message_type=parsed.get("message_type", ""),
                control_id=parsed.get("control_id", ""),
                order_control=parsed.get("order_control", ""),
                accession=parsed.get("accession", ""), action=action, error=error[:256],
                raw=(raw[:100_000] if keep_raw else ""),
            ))
            s.commit()
    except Exception as exc:  # logging must never break the intake
        log.warning("could not log the HL7 message: %s", exc)


def upsert_from_hl7(parsed: dict, *, transport: str = "http",
                    default_station_aet: str = "", default_modality: str = "",
                    raw: str = "") -> dict:
    """Apply one parsed order message. Returns {action, accession, item_id}.

    The message type is checked first: an `ORU^R01` (a report) carries OBR
    segments too, and applying it would create a worklist entry that nobody
    ordered. `hl7.describe_message_type` says why in plain words.
    """
    from . import hl7

    message_type = parsed.get("message_type", "")
    if not hl7.is_order_message(message_type):
        reason = hl7.describe_message_type(message_type)
        log_hl7(transport, parsed, "rejected", reason, raw=raw)
        return {"action": "rejected", "accession": parsed.get("accession", ""),
                "item_id": None, "error": reason}

    accession = parsed.get("accession", "")
    sps_id = parsed.get("sps_id") or "1"
    if not accession:
        log_hl7(transport, parsed, "rejected", "no accession number")
        return {"action": "rejected", "accession": "", "item_id": None,
                "error": "no accession number"}

    with session_factory()() as s:
        row = s.scalars(
            select(LocalWorklistItem).where(
                LocalWorklistItem.accession == accession,
                LocalWorklistItem.sps_id == sps_id,
            )
        ).first()

        if parsed.get("order_control", "").upper() in ("CA", "OC"):
            if row is None:
                log_hl7(transport, parsed, "cancel-unknown",
                        "no local item for this accession")
                return {"action": "cancel-unknown", "accession": accession, "item_id": None,
                        "error": "no local item for this accession"}
            s.delete(row)
            s.commit()
            publish_metrics()
            log_hl7(transport, parsed, "cancelled")
            return {"action": "cancelled", "accession": accession, "item_id": None}

        values = {
            "patient_id": parsed.get("patient_id", ""),
            "patient_name": parsed.get("patient_name", ""),
            "birth_date": parsed.get("birth_date", ""),
            "sex": parsed.get("sex", ""),
            "modality": parsed.get("modality", "") or default_modality,
            "station_aet": parsed.get("station_aet", "") or default_station_aet,
            "procedure_description": parsed.get("procedure_description", ""),
            "scheduled_date": parsed.get("scheduled_date", ""),
            "scheduled_time": parsed.get("scheduled_time", ""),
            "study_uid": parsed.get("study_uid", ""),
            "sps_status": "SCHEDULED",
            "enabled": True,
            "origin": "hl7",
        }
        mapped = parsed.get("mapped") or {}
        if row is None:
            row = LocalWorklistItem(accession=accession, sps_id=sps_id,
                                    extra_attributes=dict(mapped), **values)
            s.add(row)
            action = "created"
        else:
            for key, value in values.items():
                if value:            # never blank an existing field with an empty HL7 field
                    setattr(row, key, value)
            if mapped:
                row.extra_attributes = {**(row.extra_attributes or {}), **mapped}
            action = "updated"
        s.commit()
        item_id = row.id

    publish_metrics()
    log_hl7(transport, parsed, action, raw=raw)
    log.info("local worklist: HL7 %s %s (accession %s, transport %s)",
             parsed.get("order_control", "?"), action, accession, transport)
    return {"action": action, "accession": accession, "item_id": item_id}


def default_validity_days() -> int:
    return settings_service.get_int("local_default_validity_days")


def expiry_for(days: int | None = None) -> datetime | None:
    """Validity window for a new manual item (0 = unlimited)."""
    window = default_validity_days() if days is None else days
    if window <= 0:
        return None
    return _now() + timedelta(days=window)
