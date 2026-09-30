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

from sqlalchemy import func, select

from . import local_worklist, metrics, settings_service
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
    metrics.UPS_WORKITEMS.labels(operation="create").inc()
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
    metrics.UPS_WORKITEMS.labels(operation="state").inc()
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


# Query keys that map 1:1 onto a column of the local table, so the database can
# do the filtering. Dates and times are deliberately absent: the API renders them
# normalised (dashes/colons removed) while the column keeps what was stored —
# filtering in SQL would produce false negatives, so they stay in the exact
# check below.
_PUSHDOWN_COLUMNS = {
    "00080050": LocalWorklistItem.accession,
    "00100020": LocalWorklistItem.patient_id,
    "00100010": LocalWorklistItem.patient_name,
    "00080060": LocalWorklistItem.modality,
    "00400001": LocalWorklistItem.station_aet,
    "00401001": LocalWorklistItem.sps_id,
    "0020000D": LocalWorklistItem.study_uid,
    "00404041": LocalWorklistItem.sps_status,
    "00741000": LocalWorklistItem.sps_status,
}


def _pushdown_clauses(query: dict[str, str]) -> list:
    """WHERE clauses for the keys a column can answer (rest stays in Python)."""
    clauses = []
    for tag, value in query.items():
        column = _PUSHDOWN_COLUMNS.get(tag)
        if column is None or not value:
            continue
        needle = value.rstrip("*")
        if tag in ("00404041", "00741000"):
            # the state is compared case-insensitively (the column is free text)
            clauses.append(func.upper(column).like(f"%{needle.upper()}%"))
        else:
            clauses.append(column.ilike(f"%{needle}%"))
    return clauses


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

    # The database filters what it can (a busy house can hold thousands of local
    # items); the exact match below stays authoritative for the rest — including
    # the dates the API renders normalised and the mapped extra attributes.
    statement = select(LocalWorklistItem)
    clauses = _pushdown_clauses(query)
    if clauses:
        statement = statement.where(*clauses)
    with session_factory()() as s:
        rows = s.scalars(statement.order_by(LocalWorklistItem.id.desc())).all()

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
        result = _subscription_dict(row)
    # keep the event hub's cached scope in step (it must not query per event)
    hub.set_scope(subscriber_aet, result["workitem_uid"])
    return result


def delete_subscription(subscriber_aet: str) -> bool:
    subscriber_aet = (subscriber_aet or "").strip().upper()
    with session_factory()() as s:
        row = s.scalars(select(UpsSubscription).where(
            UpsSubscription.subscriber_aet == subscriber_aet)).first()
        if row is None:
            return False
        s.delete(row)
        s.commit()
    # a deleted subscription also drops the connected event channel
    hub.forget(subscriber_aet)
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

    The subscription *scope* (which work item a subscriber watches) is cached
    here instead of being read from the database on every event: a fan-out would
    otherwise cost one query per subscriber per event, on the DIMSE/request
    thread that just changed the state. The API keeps the cache in step through
    `set_scope`/`forget`.
    """

    # A bounded number of live subscribers: every one of them is a queue the
    # broker writes to, and nobody needs thousands of event channels.
    MAX_SUBSCRIBERS = 200

    def __init__(self) -> None:
        self._loop = None
        self._queues: dict[str, set] = {}
        self._scopes: dict[str, str] = {}
        self._lock = threading.Lock()

    def bind_loop(self, loop) -> None:
        self._loop = loop

    def subscribe(self, subscriber: str, queue) -> bool:
        """Register a connected subscriber.

        False when the subscriber has no subscription (PS3.18 §11.6: the
        subscription comes first) or the hub is full. The scope is read here,
        once per connection — not per event, which would put a query on the
        thread that just changed the work item.
        """
        subscriber = subscriber.strip().upper()
        subscription = subscription_for(subscriber)
        if subscription is None:
            return False
        with self._lock:
            if len(self._queues) >= self.MAX_SUBSCRIBERS and subscriber not in self._queues:
                return False
            self._queues.setdefault(subscriber, set()).add(queue)
            self._scopes[subscriber] = subscription["workitem_uid"]
        return True

    def unsubscribe(self, subscriber: str, queue) -> None:
        subscriber = subscriber.strip().upper()
        with self._lock:
            queues = self._queues.get(subscriber)
            if queues is None:
                return
            queues.discard(queue)
            if not queues:
                self._queues.pop(subscriber, None)
                self._scopes.pop(subscriber, None)

    def set_scope(self, subscriber: str, workitem_uid: str) -> None:
        """Remember which work item a subscriber watches (empty = all)."""
        with self._lock:
            self._scopes[subscriber.strip().upper()] = workitem_uid or ""

    def forget(self, subscriber: str) -> None:
        """Drop a subscriber completely — its subscription was deleted."""
        with self._lock:
            self._queues.pop(subscriber.strip().upper(), None)
            self._scopes.pop(subscriber.strip().upper(), None)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._queues)

    def publish(self, event: dict) -> None:
        if self._loop is None:
            return
        uid = event.get("workitem_uid", "")
        with self._lock:
            targets = [(sub, list(queues), self._scopes.get(sub, ""))
                       for sub, queues in self._queues.items()]
        delivered = 0
        for _subscriber, queues, scope in targets:
            if scope and scope != uid:
                continue                      # only interested in another item
            for queue in queues:
                try:
                    self._loop.call_soon_threadsafe(queue.put_nowait, event)
                    delivered += 1
                except RuntimeError:          # loop gone (shutdown / test teardown)
                    metrics.UPS_EVENTS.labels(result="dropped").inc()
                    return
        if targets:
            metrics.UPS_EVENTS.labels(result="delivered" if delivered else "no_subscriber").inc()

    def reset_for_tests(self) -> None:
        with self._lock:
            self._queues.clear()
            self._scopes.clear()
        self._loop = None


hub = _EventHub()
