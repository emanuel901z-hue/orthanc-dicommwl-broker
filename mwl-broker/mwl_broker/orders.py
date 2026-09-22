"""Order context: which order does an imaging study belong to?

IHE MADO (Manifest-based Access to DICOM Objects) ties an imaging manifest back
to its order through the Accession Number and the Requested Procedure. The broker
is the system in this stack that *knows* that correlation: it answered the
worklist query (which upstream knows the case), it took the MPPS step (did the
examination run?) and it routed the images (did anything arrive?).

This module collects those facts for one study or one accession number, so a
manifest creator — or an operator looking at a study — does not have to guess.
It is a **correlation service, not an archive**: no image data, no patient name.

PHI: Accession Number, SPS ID and Study Instance UID are the identifiers this
stack may match on; the patient ID comes along because it is what the correlation
runs on. The patient *name* never leaves this module (see agents.md).
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import LocalWorklistItem, MppsStep, MwlSource, SeenItem, StoreLog

log = logging.getLogger("mwl_broker.orders")

# Where a fact came from — the same words the API returns in `origins`.
ORIGIN_LOCAL = "local"
ORIGIN_WORKLIST = "worklist"
ORIGIN_MPPS = "mpps"
ORIGIN_STORE = "store"


def _rows(s: Session, model, study_uid: str, accession: str, limit: int) -> list:
    """Rows of one table matching the study UID and/or the accession number.

    Both filters together mean *both* must match: a caller who knows both wants
    the one order, not everything that matches either key.
    """
    stmt = select(model)
    if study_uid:
        stmt = stmt.where(model.study_uid == study_uid)
    if accession:
        stmt = stmt.where(model.accession == accession)
    return list(s.scalars(stmt.limit(limit)).all())


def _blank(accession: str, sps_id: str) -> dict:
    return {
        "study_uid": "",
        "accession": accession,
        "sps_id": sps_id,
        "patient_id": "",
        "modality": "",
        "station_aet": "",
        "procedure_description": "",
        "scheduled_date": "",
        "scheduled_time": "",
        "sps_status": "",
        "sources": [],
        "origins": [],
        "mpps_status": "",
        "mpps_started_at": None,
        "mpps_ended_at": None,
        "forwarded_instances": 0,
    }


def context(s: Session, study_uid: str = "", accession: str = "",
            limit: int = 50) -> list[dict]:
    """Order context for the given study UID and/or accession number.

    One entry per order — that is per `(accession, scheduled step)` pair, because
    an accession can carry several scheduled steps and a study can be reached
    through more than one worklist entry. `limit` bounds the rows read per table
    (the tables are indexed on both keys).
    """
    found: dict[tuple[str, str], dict] = {}

    def entry(acc: str, sps: str) -> dict:
        return found.setdefault((acc, sps), _blank(acc, sps))

    def note(record: dict, origin: str) -> None:
        if origin not in record["origins"]:
            record["origins"].append(origin)

    # The operator's own entries are the richest source: they carry the whole
    # order (procedure, schedule, station) and exist even without a RIS.
    for item in _rows(s, LocalWorklistItem, study_uid, accession, limit):
        record = entry(item.accession, item.sps_id)
        record["study_uid"] = record["study_uid"] or item.study_uid
        record["patient_id"] = record["patient_id"] or item.patient_id
        record["modality"] = record["modality"] or item.modality
        record["station_aet"] = record["station_aet"] or item.station_aet
        record["procedure_description"] = (
            record["procedure_description"] or item.procedure_description
        )
        record["scheduled_date"] = record["scheduled_date"] or item.scheduled_date
        record["scheduled_time"] = record["scheduled_time"] or item.scheduled_time
        record["sps_status"] = item.sps_status or record["sps_status"]
        note(record, ORIGIN_LOCAL)

    # What the modality reported. The newest step wins — it is the state the RIS
    # is waiting for, and it says whether the order is still open.
    for step in _rows(s, MppsStep, study_uid, accession, limit):
        record = entry(step.accession, step.sps_id)
        record["study_uid"] = record["study_uid"] or step.study_uid
        record["patient_id"] = record["patient_id"] or step.patient_id
        record["modality"] = record["modality"] or step.modality
        record["station_aet"] = record["station_aet"] or step.station_aet
        record["mpps_status"] = step.status
        record["mpps_started_at"] = step.started_at or record["mpps_started_at"]
        record["mpps_ended_at"] = step.ended_at or record["mpps_ended_at"]
        note(record, ORIGIN_MPPS)

    # Which upstream worklist source this order came from — the answer to "where
    # does this study belong?" that the routing already uses.
    source_names = {row.id: row.name for row in s.scalars(select(MwlSource)).all()}
    for seen in _rows(s, SeenItem, study_uid, accession, limit):
        record = entry(seen.accession, seen.sps_id)
        record["study_uid"] = record["study_uid"] or seen.study_uid
        record["patient_id"] = record["patient_id"] or seen.patient_id
        name = source_names.get(seen.source_id)
        if name and name not in record["sources"]:
            record["sources"].append(name)
        note(record, ORIGIN_WORKLIST)

    # Images the broker already forwarded carry no scheduled step, so they are
    # aggregated per accession and attached to whatever entry that accession has.
    # An accession nobody else knows is still worth reporting: that is the
    # "images arrived, order unknown" case an operator has to chase.
    forwarded: dict[str, dict] = {}
    for store in _rows(s, StoreLog, study_uid, accession, limit):
        agg = forwarded.setdefault(store.accession, {"count": 0, "study_uid": ""})
        agg["count"] += 1
        agg["study_uid"] = agg["study_uid"] or store.study_uid

    for acc, agg in forwarded.items():
        matching = [r for (a, _), r in found.items() if a == acc]
        if not matching:
            matching = [entry(acc, "")]
        for record in matching:
            record["study_uid"] = record["study_uid"] or agg["study_uid"]
            record["forwarded_instances"] += agg["count"]
            note(record, ORIGIN_STORE)

    return [found[key] for key in sorted(found)]
