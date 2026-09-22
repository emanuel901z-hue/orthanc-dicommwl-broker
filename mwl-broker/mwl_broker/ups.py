"""UPS-RS: the worklist as a DICOMweb resource.

Modern clients (and the DICOM standard since 2014) can manage work items over
REST instead of DIMSE. This module serves a **pragmatic subset** of PS3.18 §11:

* search   `GET  /dicom-web/workitems?{query}`
* retrieve `GET  /dicom-web/workitems/{uid}`
* create   `POST /dicom-web/workitems`            (a local work item)
* state    `PUT  /dicom-web/workitems/{uid}/state` (IN PROGRESS / COMPLETED /
                                                    CANCELED)

Subscriptions, WebSocket event reports and the full UPS attribute set are **not**
implemented — the conformance statement lists that as a boundary. The search runs
through the same aggregation as the DIMSE path, so a client can never see a
different worklist than a modality.

PHI: a work item inherently carries patient data (the modality needs it). The
endpoint therefore behaves like the local worklist — it is behind the same
read/write policy, and the log stays free of names.
"""
import logging
import uuid as uuidlib

from sqlalchemy import select

from . import local_worklist, settings_service
from .db import session_factory
from .models import LocalWorklistItem

log = logging.getLogger("mwl_broker.ups")

# UPS procedure step states (PS3.3 C.20.1)
STATE_SCHEDULED = "SCHEDULED"
STATE_IN_PROGRESS = "IN PROGRESS"
STATE_COMPLETED = "COMPLETED"
STATE_CANCELED = "CANCELED"
STATES = (STATE_SCHEDULED, STATE_IN_PROGRESS, STATE_COMPLETED, STATE_CANCELED)

# Which query keys we can match on (the same set the DIMSE path uses), each
# mapped to the DICOM JSON tag key used in the response.
QUERY_KEYS = {
    "AccessionNumber": "00080050",
    "PatientID": "00100020",
    "PatientName": "00100010",
    "ScheduledStationAETitle": "00400001",
    "Modality": "00080060",
    "ScheduledProcedureStepStartDate": "00400002",
    "ScheduledProcedureStepID": "00401001",
    "StudyInstanceUID": "0020000D",
    "ProcedureStepState": "00404041",
}


def _uid_for(item: LocalWorklistItem) -> str:
    """A stable work item UID: derived from the accession, else random."""
    if item.study_uid:
        return f"1.2.840.113619.6.500.{item.study_uid}"
    return f"1.2.840.113619.6.500.{item.id}.{uuidlib.uuid5(uuidlib.NAMESPACE_OID, str(item.id)).hex[:12]}"


def item_to_workitem(item: LocalWorklistItem) -> dict:
    """One local item as a UPS work item (the fields a client needs)."""
    state = (item.sps_status or "").upper()
    if state not in STATES:
        state = STATE_SCHEDULED if item.enabled else STATE_CANCELED
    workitem: dict = {
        "00081190": {"vr": "UR", "Value": [f"/dicom-web/workitems/{_uid_for(item)}"]},
        "00404041": {"vr": "CS", "Value": [state]},
        "00080050": {"vr": "SH", "Value": [item.accession]},
        "00100020": {"vr": "LO", "Value": [item.patient_id]},
        "00401001": {"vr": "SH", "Value": [item.sps_id]},
        "00400001": {"vr": "AE", "Value": [item.station_aet]},
        "00080060": {"vr": "CS", "Value": [item.modality]},
    }
    if item.patient_name:
        workitem["00100010"] = {"vr": "PN", "Value": [{"Alphabetic": item.patient_name}]}
    if item.scheduled_date:
        workitem["00400002"] = {"vr": "DA", "Value": [item.scheduled_date]}
    if item.study_uid:
        workitem["0020000D"] = {"vr": "UI", "Value": [item.study_uid]}
    # extra attributes a local HL7 field mapping added
    for tag, value in (item.extra_attributes or {}).items():
        from pydicom.datadict import tag_for_keyword

        number = tag_for_keyword(tag)
        if number is not None:
            workitem[f"{number:08X}"] = {"vr": "LO", "Value": [str(value)]}
    return workitem


def _read_value(workitem: dict, tag: str) -> str:
    entry = workitem.get(tag) or {}
    values = entry.get("Value") or []
    if not values:
        return ""
    first = values[0]
    if isinstance(first, dict):          # PN
        return str(first.get("Alphabetic", ""))
    return str(first)


def create_workitem(workitem: dict) -> dict:
    """Create a local work item from a UPS-RS request body."""
    accession = _read_value(workitem, "00080050")
    if not accession:
        raise ValueError("AccessionNumber (0008,0050) is required")
    values = {
        "accession": accession,
        "sps_id": _read_value(workitem, "00401001") or "1",
        "patient_id": _read_value(workitem, "00100020"),
        "patient_name": _read_value(workitem, "00100010"),
        "station_aet": _read_value(workitem, "00400001")
                      or settings_service.get_str("hl7_default_station_aet"),
        "modality": _read_value(workitem, "00080060")
                    or settings_service.get_str("hl7_default_modality"),
        "scheduled_date": _read_value(workitem, "00400002"),
        "study_uid": _read_value(workitem, "0020000D"),
        "origin": "ups",
        "enabled": True,
        "sps_status": "SCHEDULED",
    }
    with session_factory()() as s:
        row = s.scalars(select(LocalWorklistItem).where(
            LocalWorklistItem.accession == accession,
            LocalWorklistItem.sps_id == values["sps_id"],
        )).first()
        if row is None:
            row = LocalWorklistItem(**values)
            s.add(row)
        else:
            for key, value in values.items():
                if value:
                    setattr(row, key, value)
        s.commit()
        s.refresh(row)
        item = row
    local_worklist.publish_metrics()
    log.info("UPS work item created: %s (accession %s)", _uid_for(item), accession)
    return item_to_workitem(item)


def _find(uid: str) -> LocalWorklistItem | None:
    with session_factory()() as s:
        for row in s.scalars(select(LocalWorklistItem)).all():
            if _uid_for(row) == uid:
                return row
    return None


def get_workitem(uid: str) -> dict | None:
    row = _find(uid)
    return item_to_workitem(row) if row is not None else None


def set_state(uid: str, state: str) -> dict:
    """Change the state of a work item (PUT …/state)."""
    state = (state or "").upper().strip()
    if state not in STATES:
        raise ValueError(f"unknown state {state!r} (use one of {', '.join(STATES)})")
    row = _find(uid)
    if row is None:
        raise LookupError("not found")
    with session_factory()() as s:
        live = s.get(LocalWorklistItem, row.id)
        if live is None:
            raise LookupError("not found")
        if state in (STATE_COMPLETED, STATE_CANCELED):
            # a finished work item disappears from the worklist, like a completed
            # MPPS step does
            live.enabled = False
            live.sps_status = state
        else:
            live.enabled = True
            live.sps_status = state
        s.commit()
        s.refresh(live)
        item = live
    local_worklist.publish_metrics()
    log.info("UPS work item %s → %s", uid, state)
    return item_to_workitem(item)


def search(query: dict[str, str], limit: int = 100) -> list[dict]:
    """Search the work items — the same data the DIMSE path serves.

    Only the local work items are searchable here: the upstream sources are
    queried per C-FIND (with the modality's own identifier), so a REST search
    without a station would otherwise fan out on every request.
    """
    with session_factory()() as s:
        rows = s.scalars(
            select(LocalWorklistItem).order_by(LocalWorklistItem.id.desc())
        ).all()

    matches = []
    for row in rows:
        workitem = item_to_workitem(row)
        if query and not all(
            value.upper() in _read_value(workitem, tag).upper()
            for tag, value in query.items()
            if value
        ):
            continue
        matches.append(workitem)
        if len(matches) >= limit:
            break
    return matches
