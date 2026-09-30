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
import threading
import uuid as uuidlib

from sqlalchemy import select

from . import local_worklist, settings_service
from .db import session_factory
from .models import LocalWorklistItem, UpsSubscription

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
    "PatientBirthDate": "00100030",
    "ScheduledStationAETitle": "00400001",
    "Modality": "00080060",
    "ScheduledProcedureStepStartDate": "00400002",
    "ScheduledProcedureStepStartTime": "00400003",
    "ScheduledProcedureStepID": "00401001",
    "RequestedProcedureID": "00401001",
    "RequestedProcedureDescription": "00321060",
    "StudyInstanceUID": "0020000D",
    "ProcedureStepState": "00404041",
    # the standard UPS state attribute (PS3.4 CC.2.5); we emit both
    "UnifiedProcedureStepState": "00741000",
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
        # (0040,4041) is what the broker has always served; (0074,1000) is the
        # attribute the UPS standard (PS3.4 CC.2.5) defines. Both carry the state
        # so a standard client finds the right one and existing consumers keep
        # working — see the conformance statement.
        "00404041": {"vr": "CS", "Value": [state]},
        "00741000": {"vr": "CS", "Value": [state]},
        "00080050": {"vr": "SH", "Value": [item.accession]},
        "00100020": {"vr": "LO", "Value": [item.patient_id]},
        "00401001": {"vr": "SH", "Value": [item.sps_id]},
        "00400001": {"vr": "AE", "Value": [item.station_aet]},
        "00080060": {"vr": "CS", "Value": [item.modality]},
    }
    if item.patient_name:
        workitem["00100010"] = {"vr": "PN", "Value": [{"Alphabetic": item.patient_name}]}
    if item.birth_date:
        workitem["00100030"] = {"vr": "DA", "Value": [item.birth_date.replace("-", "")]}
    if item.sex:
        workitem["00100040"] = {"vr": "CS", "Value": [item.sex]}
    if item.scheduled_date:
        workitem["00400002"] = {"vr": "DA", "Value": [item.scheduled_date.replace("-", "")]}
    if item.scheduled_time:
        workitem["00400003"] = {"vr": "TM", "Value": [item.scheduled_time.replace(":", "")]}
    if item.procedure_description:
        workitem["00321060"] = {"vr": "LO", "Value": [item.procedure_description]}
        workitem["00400007"] = {"vr": "LO", "Value": [item.procedure_description]}
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


def _normalize_date(value: str) -> str:
    """A DICOM DA (YYYYMMDD) as the local model stores it (YYYY-MM-DD)."""
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return value or ""


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
        "birth_date": _normalize_date(_read_value(workitem, "00100030")),
        "sex": _read_value(workitem, "00100040"),
        "station_aet": _read_value(workitem, "00400001")
                      or settings_service.get_str("hl7_default_station_aet"),
        "modality": _read_value(workitem, "00080060")
                    or settings_service.get_str("hl7_default_modality"),
        "procedure_description": (_read_value(workitem, "00321060")
                                  or _read_value(workitem, "00400007")),
        "scheduled_date": _read_value(workitem, "00400002"),
        "scheduled_time": _read_value(workitem, "00400003"),
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
    workitem = item_to_workitem(item)
    hub.publish({"event": "workitem-created", "workitem_uid": _uid_for(item),
                 "state": workitem["00404041"]["Value"][0], "workitem": workitem})
    return workitem


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
    workitem = item_to_workitem(item)
    hub.publish({"event": "workitem-state-change", "workitem_uid": uid,
                 "state": state, "workitem": workitem})
    return workitem


def _dedupe_key(workitem: dict) -> tuple[str, str]:
    return (_read_value(workitem, "00080050"), _read_value(workitem, "00401001"))


def _workitem_matches(workitem: dict, query: dict[str, str]) -> bool:
    return all(
        value.upper() in _read_value(workitem, tag).upper()
        for tag, value in query.items()
        if value
    )


def _identifier_from_query(query: dict[str, str]) -> "Dataset":
    """A C-FIND identifier from the REST query, for the upstream fan-out."""
    from pydicom.datadict import keyword_for_tag
    from pydicom.dataset import Dataset

    identifier = Dataset()
    identifier.QueryRetrieveLevel = "WORKLIST"
    for tag, value in query.items():
        keyword = keyword_for_tag(int(tag, 16))
        if keyword:
            setattr(identifier, keyword, value)
    return identifier


def _derived_uid(accession: str, sps_id: str, study_uid: str) -> str:
    if study_uid:
        return f"1.2.840.113619.6.500.{study_uid}"
    seed = f"{accession}|{sps_id}"
    return f"1.2.840.113619.6.500.{uuidlib.uuid5(uuidlib.NAMESPACE_OID, seed).hex[:20]}"


def dataset_to_workitem(ds) -> dict:
    """Flatten an upstream MWL answer into the same flat UPS view as local items.

    The upstream answers use the Modality Worklist information model (a
    Scheduled Procedure Step sequence); UPS work items are flat. Without the
    flattening a REST client would get two different shapes from one search.
    """
    sps = None
    sequence = getattr(ds, "ScheduledProcedureStepSequence", None)
    if sequence:
        sps = sequence[0]

    def value(obj, name: str) -> str:
        if obj is None:
            return ""
        raw = obj.get(name, "")
        return str(raw) if raw not in (None, "") else ""

    accession = value(ds, "AccessionNumber")
    sps_id = value(sps, "ScheduledProcedureStepID") or value(ds, "RequestedProcedureID") or "1"
    state = (value(sps, "ScheduledProcedureStepStatus") or STATE_SCHEDULED).upper()
    if state not in STATES:
        state = STATE_SCHEDULED
    study_uid = value(ds, "StudyInstanceUID")
    uid = _derived_uid(accession, sps_id, study_uid)
    workitem: dict = {
        "00081190": {"vr": "UR", "Value": [f"/dicom-web/workitems/{uid}"]},
        "00404041": {"vr": "CS", "Value": [state]},
        "00741000": {"vr": "CS", "Value": [state]},
        "00080050": {"vr": "SH", "Value": [accession]},
        "00100020": {"vr": "LO", "Value": [value(ds, "PatientID")]},
        "00401001": {"vr": "SH", "Value": [sps_id]},
        "00400001": {"vr": "AE", "Value": [value(sps, "ScheduledStationAETitle")]},
        "00080060": {"vr": "CS", "Value": [value(sps, "Modality") or value(ds, "Modality")]},
    }
    if value(ds, "PatientName"):
        workitem["00100010"] = {"vr": "PN", "Value": [{"Alphabetic": value(ds, "PatientName")}]}
    if value(ds, "PatientBirthDate"):
        workitem["00100030"] = {"vr": "DA", "Value": [value(ds, "PatientBirthDate")]}
    if value(ds, "PatientSex"):
        workitem["00100040"] = {"vr": "CS", "Value": [value(ds, "PatientSex")]}
    if value(sps, "ScheduledProcedureStepStartDate"):
        workitem["00400002"] = {"vr": "DA", "Value": [value(sps, "ScheduledProcedureStepStartDate")]}
    if value(sps, "ScheduledProcedureStepStartTime"):
        workitem["00400003"] = {"vr": "TM", "Value": [value(sps, "ScheduledProcedureStepStartTime")]}
    description = (value(sps, "ScheduledProcedureStepDescription")
                   or value(ds, "RequestedProcedureDescription"))
    if description:
        workitem["00321060"] = {"vr": "LO", "Value": [description]}
        workitem["00400007"] = {"vr": "LO", "Value": [description]}
    if study_uid:
        workitem["0020000D"] = {"vr": "UI", "Value": [study_uid]}
    return workitem


def _upstream_items(query: dict[str, str]) -> list:
    """Ask the sources — the same aggregation the DIMSE path uses."""
    from . import aggregation

    identifier = _identifier_from_query(query)
    # count_metrics=False: a REST search is not a modality C-FIND and must not
    # move the C-FIND counters. store_cache stays on — the search is a real
    # query and refreshes the outage bridge like any other.
    return aggregation.collect(identifier, store_cache=True, count_metrics=False).items


def search(query: dict[str, str], limit: int = 100, include_upstream: bool = False) -> list[dict]:
    """Search the work items — local entries and, optionally, the sources.

    Without `include_upstream` only the items the broker holds itself are
    searched. With it the sources are queried through the **same aggregation**
    as the DIMSE path, so a REST client never sees a different worklist than a
    modality — only the transport differs.
    """
    matches: list[dict] = []
    seen: set[tuple[str, str]] = set()

    with session_factory()() as s:
        rows = s.scalars(
            select(LocalWorklistItem).order_by(LocalWorklistItem.id.desc())
        ).all()

    for row in rows:
        workitem = item_to_workitem(row)
        if not _workitem_matches(workitem, query):
            continue
        matches.append(workitem)
        seen.add(_dedupe_key(workitem))
        if len(matches) >= limit:
            return matches

    if include_upstream:
        for ds in _upstream_items(query):
            workitem = dataset_to_workitem(ds)
            key = _dedupe_key(workitem)
            if key in seen or not _workitem_matches(workitem, query):
                continue
            seen.add(key)
            matches.append(workitem)
            if len(matches) >= limit:
                break
    return matches


# ── subscriptions + the event channel (PS3.18 §11.6) ───────────────────


def _subscription_dict(row: UpsSubscription) -> dict:
    return {
        "id": row.id,
        "subscriber_aet": row.subscriber_aet,
        "workitem_uid": row.workitem_uid,
        "deletion_lock": row.deletion_lock,
        "created_at": row.created_at,
    }


def list_subscriptions() -> list[dict]:
    with session_factory()() as s:
        rows = s.scalars(select(UpsSubscription).order_by(UpsSubscription.id)).all()
        return [_subscription_dict(row) for row in rows]


def subscription_for(subscriber_aet: str) -> dict | None:
    with session_factory()() as s:
        row = s.scalars(select(UpsSubscription).where(
            UpsSubscription.subscriber_aet == subscriber_aet)).first()
        return _subscription_dict(row) if row is not None else None


def upsert_subscription(subscriber_aet: str, workitem_uid: str = "",
                        deletion_lock: bool = False) -> dict:
    """Create or replace the subscription of one subscriber."""
    subscriber_aet = (subscriber_aet or "").strip().upper()
    if not subscriber_aet:
        raise ValueError("subscriber_aet is required")
    with session_factory()() as s:
        row = s.scalars(select(UpsSubscription).where(
            UpsSubscription.subscriber_aet == subscriber_aet)).first()
        if row is None:
            row = UpsSubscription(subscriber_aet=subscriber_aet)
            s.add(row)
        row.workitem_uid = (workitem_uid or "").strip()
        row.deletion_lock = bool(deletion_lock)
        s.commit()
        s.refresh(row)
        return _subscription_dict(row)


def delete_subscription(subscriber_aet: str) -> bool:
    with session_factory()() as s:
        row = s.scalars(select(UpsSubscription).where(
            UpsSubscription.subscriber_aet == (subscriber_aet or "").strip().upper())).first()
        if row is None:
            return False
        s.delete(row)
        s.commit()
        return True


class _EventHub:
    """Fan-out of work item events to subscribers on the broker's WebSocket.

    PS3.18 §11.6 has the subscriber hand the broker a notification channel URL —
    a full DICOM event-report transport. This broker delivers the same event as
    JSON to subscribers that are connected to **its own** WebSocket
    (`/dicom-web/workitems/ws`); the boundary is in the conformance statement.

    A state change happens on a request/DIMSE thread, the WebSocket lives on the
    event loop: `publish` therefore hands the event to the loop thread with
    `call_soon_threadsafe` instead of touching the queues from the wrong thread.
    """

    def __init__(self) -> None:
        self._loop = None
        self._queues: dict[str, set] = {}
        self._lock = threading.Lock()

    def bind_loop(self, loop) -> None:
        self._loop = loop

    def subscribe(self, subscriber: str, queue) -> None:
        with self._lock:
            self._queues.setdefault(subscriber.strip().upper(), set()).add(queue)

    def unsubscribe(self, subscriber: str, queue) -> None:
        with self._lock:
            self._queues.get(subscriber.strip().upper(), set()).discard(queue)

    def publish(self, event: dict) -> None:
        if self._loop is None:
            return
        uid = event.get("workitem_uid", "")
        with self._lock:
            targets = list(self._queues.items())
        for subscriber, queues in targets:
            subscription = subscription_for(subscriber)
            if subscription is None:
                continue                      # not subscribed (any more)
            if subscription["workitem_uid"] and subscription["workitem_uid"] != uid:
                continue                      # only interested in another item
            for queue in queues:
                try:
                    self._loop.call_soon_threadsafe(queue.put_nowait, event)
                except RuntimeError:          # loop gone (shutdown / test teardown)
                    return

    def reset_for_tests(self) -> None:
        with self._lock:
            self._queues.clear()
        self._loop = None


hub = _EventHub()
