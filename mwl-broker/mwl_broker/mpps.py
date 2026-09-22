"""MPPS — accept performed procedure steps and report them back to the RIS.

A modality that performs an examination reports it as MPPS (Modality Performed
Procedure Step): N-CREATE with status IN PROGRESS, later N-SET with COMPLETED or
DISCONTINUED. The RIS normally closes the order from that message. When the RIS
cannot receive MPPS itself (which is exactly the case this broker exists for),
the broker takes the step and reports the state back as an HL7 message.

Two rules from the project apply here as everywhere:

* the DICOM path must never block — forwarding happens in a background thread,
  failures are counted and retried from the API, never on the wire;
* PHI stays out of the logs — only the patient *ID* is stored (like
  `seen_items`), never the name.
"""
import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import select

from . import metrics, settings_service
from .db import session_factory
from .models import MppsStep

log = logging.getLogger("mwl_broker.mpps")

STATUS_IN_PROGRESS = "IN PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_DISCONTINUED = "DISCONTINUED"
STATUSES = (STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_DISCONTINUED)

# MPPS status → HL7 order/result status for the message back to the RIS.
# Z01/Z02 are the "exam started/ended" triggers of the IHE SWF profile; the
# result status is the ORU convention the RIS needs to close the order.
HL7_STATUS = {
    STATUS_IN_PROGRESS: ("Z01", "IP"),      # in progress
    STATUS_COMPLETED: ("Z02", "CM"),        # completed
    STATUS_DISCONTINUED: ("Z03", "CA"),     # cancelled/discontinued
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enabled() -> bool:
    return settings_service.get_bool("mpps_enabled")


def forwarding_enabled() -> bool:
    return enabled() and settings_service.get_bool("mpps_forward_enabled")


def hide_completed() -> bool:
    return settings_service.get_bool("mpps_hide_completed")


def _text(ds, tag: str) -> str:
    """Read a tag as text; MPPS attributes are often nested in sequences."""
    value = ds.get(tag, "")
    return str(value or "").strip()


def parse_step(ds) -> dict:
    """Pull the identifiers out of an MPPS dataset (create or update)."""
    sps_seq = ds.get("ScheduledStepAttributesSequence") or []
    sps = sps_seq[0] if sps_seq else None
    accession = _text(ds, "AccessionNumber") or (_text(sps, "AccessionNumber") if sps else "")
    patient_id = _text(ds, "PatientID") or (_text(sps, "PatientID") if sps else "")
    study_uid = _text(ds, "StudyInstanceUID") or (_text(sps, "StudyInstanceUID") if sps else "")
    sps_id = _text(sps, "ScheduledProcedureStepID") if sps else ""
    station = _text(sps, "ScheduledStationAETitle") if sps else ""
    modality = _text(sps, "Modality") if sps else ""
    perf_seq = ds.get("PerformedSeriesSequence") or []
    return {
        "accession": accession,
        "patient_id": patient_id,
        "study_uid": study_uid,
        "sps_id": sps_id,
        "station_aet": station,
        "modality": modality or _text(ds, "Modality"),
        "performed_procedure_step_id": _text(ds, "PerformedProcedureStepID"),
        "series": len(perf_seq),
    }


def record_create(sop_instance_uid: str, ds) -> dict:
    """N-CREATE: the examination started. Returns the stored step."""
    fields = parse_step(ds)
    started = _text(ds, "PerformedProcedureStepStartDate")
    start_time = _text(ds, "PerformedProcedureStepStartTime")
    with session_factory()() as s:
        row = s.scalars(
            select(MppsStep).where(MppsStep.sop_instance_uid == sop_instance_uid)
        ).first()
        if row is None:
            row = MppsStep(sop_instance_uid=sop_instance_uid)
            s.add(row)
        row.status = STATUS_IN_PROGRESS
        for key in ("accession", "patient_id", "study_uid", "sps_id", "station_aet",
                    "modality", "performed_procedure_step_id"):
            if fields.get(key):
                setattr(row, key, fields[key])
        row.started_at = _combine(started, start_time) or _now()
        row.forwarded = False
        row.forward_error = ""
        s.commit()
        s.refresh(row)
        step = _as_dict(row)
    metrics.MPPS_STEPS.labels(status="created").inc()
    log.info("MPPS created: %s (accession=%s station=%s)",
             sop_instance_uid, step["accession"] or "-", step["station_aet"] or "-")
    if forwarding_enabled():
        forward_async(step["id"])
    return step


def record_update(sop_instance_uid: str, ds) -> dict:
    """N-SET: status change (COMPLETED / DISCONTINUED)."""
    status = _text(ds, "PerformedProcedureStepStatus").upper() or STATUS_COMPLETED
    if status not in STATUSES:
        status = STATUS_COMPLETED
    fields = parse_step(ds)
    ended = _text(ds, "PerformedProcedureStepEndDate")
    end_time = _text(ds, "PerformedProcedureStepEndTime")
    with session_factory()() as s:
        row = s.scalars(
            select(MppsStep).where(MppsStep.sop_instance_uid == sop_instance_uid)
        ).first()
        if row is None:
            # a modality that never sent N-CREATE (or the broker restarted):
            # record what we have instead of losing the event
            row = MppsStep(sop_instance_uid=sop_instance_uid, started_at=_now())
            s.add(row)
            log.warning("MPPS update without a prior create: %s", sop_instance_uid)
        row.status = status
        for key in ("accession", "patient_id", "study_uid", "sps_id", "station_aet",
                    "modality", "performed_procedure_step_id"):
            if fields.get(key):
                setattr(row, key, fields[key])
        if status != STATUS_IN_PROGRESS:
            row.ended_at = _combine(ended, end_time) or _now()
        row.forwarded = False
        row.forward_error = ""
        s.commit()
        s.refresh(row)
        step = _as_dict(row)
    metrics.MPPS_STEPS.labels(status=status.lower().replace(" ", "_")).inc()
    log.info("MPPS %s: %s (accession=%s)", status.lower(), sop_instance_uid,
             step["accession"] or "-")
    if forwarding_enabled():
        forward_async(step["id"])
    return step


def _combine(date: str, time: str) -> datetime | None:
    """DICOM DA+TM ("20260921" + "101530") → datetime (UTC), best effort."""
    date = "".join(ch for ch in date if ch.isdigit())
    time = "".join(ch for ch in time if ch.isdigit())
    if len(date) != 8:
        return None
    time = (time + "000000")[:6]
    try:
        return datetime(int(date[0:4]), int(date[4:6]), int(date[6:8]),
                        int(time[0:2]), int(time[2:4]), int(time[4:6]),
                        tzinfo=timezone.utc)
    except ValueError:
        return None


def _as_dict(row: MppsStep) -> dict:
    return {
        "id": row.id,
        "ts": row.ts,
        "sop_instance_uid": row.sop_instance_uid,
        "status": row.status,
        "accession": row.accession,
        "patient_id": row.patient_id,
        "sps_id": row.sps_id,
        "station_aet": row.station_aet,
        "modality": row.modality,
        "study_uid": row.study_uid,
        "performed_procedure_step_id": row.performed_procedure_step_id,
        "started_at": row.started_at,
        "ended_at": row.ended_at,
        "forwarded": row.forwarded,
        "forward_error": row.forward_error,
        "forward_attempts": row.forward_attempts,
        "forwarded_at": row.forwarded_at,
    }


def list_steps(limit: int = 100, offset: int = 0, status: str = "") -> list[dict]:
    with session_factory()() as s:
        query = select(MppsStep).order_by(MppsStep.ts.desc(), MppsStep.id.desc())
        if status:
            query = query.where(MppsStep.status == status.upper())
        rows = s.scalars(query.offset(offset).limit(limit)).all()
        return [_as_dict(r) for r in rows]


def get_step(step_id: int) -> dict | None:
    with session_factory()() as s:
        row = s.get(MppsStep, step_id)
        return _as_dict(row) if row is not None else None


def get_step_by_uid(sop_instance_uid: str) -> dict | None:
    """One step by its SOP instance UID (used by N-GET)."""
    with session_factory()() as s:
        row = s.scalars(
            select(MppsStep).where(MppsStep.sop_instance_uid == sop_instance_uid)
        ).first()
        return _as_dict(row) if row is not None else None


def to_dataset(step: dict):
    """The step as a DICOM dataset — what a modality expects from N-GET."""
    from pydicom.dataset import Dataset

    ds = Dataset()
    ds.SOPInstanceUID = step["sop_instance_uid"]
    ds.PerformedProcedureStepStatus = step["status"]
    if step.get("performed_procedure_step_id"):
        ds.PerformedProcedureStepID = step["performed_procedure_step_id"]
    if step.get("started_at"):
        started = step["started_at"]
        ds.PerformedProcedureStepStartDate = started.strftime("%Y%m%d")
        ds.PerformedProcedureStepStartTime = started.strftime("%H%M%S")
    if step.get("ended_at"):
        ended = step["ended_at"]
        ds.PerformedProcedureStepEndDate = ended.strftime("%Y%m%d")
        ds.PerformedProcedureStepEndTime = ended.strftime("%H%M%S")
    if step.get("study_uid"):
        ds.StudyInstanceUID = step["study_uid"]
    sps = Dataset()
    if step.get("accession"):
        sps.AccessionNumber = step["accession"]
    if step.get("sps_id"):
        sps.ScheduledProcedureStepID = step["sps_id"]
    if step.get("station_aet"):
        sps.ScheduledStationAETitle = step["station_aet"]
    if step.get("modality"):
        sps.Modality = step["modality"]
    ds.ScheduledStepAttributesSequence = [sps]
    return ds


def stats() -> dict:
    """Counts for the dashboard: how many steps, how many forwarded."""
    with session_factory()() as s:
        rows = s.scalars(select(MppsStep)).all()
    by_status: dict[str, int] = {}
    by_modality: dict[str, int] = {}
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        key = row.modality or "(unbekannt)"
        by_modality[key] = by_modality.get(key, 0) + 1
    pending = [r for r in rows if not r.forwarded and r.status != STATUS_IN_PROGRESS]
    return {
        "total": len(rows),
        "by_status": by_status,
        # "which modality reports nothing?" is the operator's question
        "by_modality": dict(sorted(by_modality.items(), key=lambda kv: -kv[1])),
        "forwarded": sum(1 for r in rows if r.forwarded),
        "pending_forward": len(pending),
        "last_error": next((r.forward_error for r in rows if r.forward_error), ""),
        "forward_enabled": forwarding_enabled(),
        "hide_completed": hide_completed(),
    }


def completed_identifiers() -> set[str]:
    """Accessions whose step is finished — hidden from the served worklist."""
    with session_factory()() as s:
        rows = s.scalars(
            select(MppsStep).where(MppsStep.status != STATUS_IN_PROGRESS)
        ).all()
    return {r.accession for r in rows if r.accession}


# ── Rückmeldung an das RIS ─────────────────────────────────────────────────

def build_status_message(step: dict) -> str:
    """ORU^R01 carrying the MPPS state — what the RIS needs to close the order."""
    trigger, result_status = HL7_STATUS.get(step["status"], ("Z02", "CM"))
    now = _now().strftime("%Y%m%d%H%M%S")
    control_id = f"MPPS{step['id']}{now[-6:]}"
    # MSH-1 is the field separator itself, so the field indexes are shifted by one
    segments = [
        f"MSH|^~\\&|MWLBROKER|{step.get('station_aet') or 'BROKER'}|RIS||{now}||"
        f"ORU^R01^{trigger}|{control_id}|P|2.4",
        f"PID|1||{step.get('patient_id') or ''}",
        f"ORC|SC|{step.get('accession') or ''}|{step.get('sps_id') or ''}||||||||||"
        f"{step.get('station_aet') or ''}",
        f"OBR|1|{step.get('accession') or ''}|{step.get('sps_id') or ''}|||"
        f"{step.get('started_at') or ''}|||{step.get('ended_at') or ''}|||||||||"
        f"{step.get('performed_procedure_step_id') or ''}||{result_status}",
        f"ZDS|1|{step.get('sop_instance_uid')}|MPPS|{step.get('status')}",
    ]
    return "\r".join(segments) + "\r"


def _deliver(step: dict) -> tuple[bool, str]:
    """Send the message — MLLP to the RIS or an HTTP webhook."""
    transport = (settings_service.get_str("mpps_forward_transport") or "mllp").strip().lower()
    message = build_status_message(step)
    if transport == "webhook":
        url = settings_service.get_str("mpps_forward_url").strip()
        if not url:
            return False, "no webhook URL configured"
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            url, data=message.encode("utf-8"),
            headers={"Content-Type": "text/plain", "X-MWL-Event": "mpps"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if 200 <= response.status < 300:
                    return True, ""
                return False, f"HTTP {response.status}"
        except urllib.error.URLError as exc:
            return False, str(exc)[:200]

    host = settings_service.get_str("mpps_forward_host").strip()
    port = settings_service.get_int("mpps_forward_port")
    if not host:
        return False, "no RIS host configured"
    import socket

    framed = b"\x0b" + message.encode("utf-8") + b"\x1c\x0d"
    try:
        with socket.create_connection((host, port), timeout=10) as conn:
            conn.sendall(framed)
            conn.settimeout(10)
            ack = conn.recv(4096)
    except OSError as exc:
        return False, str(exc)[:200]
    if not ack:
        return False, "no acknowledgement from the RIS"
    text = ack.decode("utf-8", "replace")
    if "MSA|AA" in text or "MSA|CA" in text:
        return True, ""
    return False, f"RIS answered with an error: {text.strip()[:120]}"


def forward(step_id: int) -> dict:
    """Deliver one step's state now (also used by the retry endpoint)."""
    step = get_step(step_id)
    if step is None:
        return {"ok": False, "error": "not found"}
    ok, error = _deliver(step)
    with session_factory()() as s:
        row = s.get(MppsStep, step_id)
        if row is not None:
            row.forward_attempts += 1
            row.forward_error = "" if ok else error
            if ok:
                row.forwarded = True
                row.forwarded_at = _now()
            s.commit()
    if ok:
        metrics.MPPS_FORWARDED.labels(result="ok").inc()
    else:
        metrics.MPPS_FORWARDED.labels(result="failed").inc()
        log.warning("MPPS state for step %s not delivered: %s", step_id, error)
    return {"ok": ok, "error": error}


def forward_async(step_id: int) -> None:
    """Never let a slow RIS delay the DICOM answer — hand it to a thread."""
    threading.Thread(target=forward, args=(step_id,), daemon=True).start()


def forward_pending(limit: int = 50) -> dict:
    """Retry everything that was not delivered yet (operator action)."""
    with session_factory()() as s:
        rows = s.scalars(
            select(MppsStep)
            .where(MppsStep.forwarded.is_(False), MppsStep.status != STATUS_IN_PROGRESS)
            .order_by(MppsStep.ts)
            .limit(limit)
        ).all()
        ids = [r.id for r in rows]
    sent, failed = 0, 0
    for step_id in ids:
        if forward(step_id)["ok"]:
            sent += 1
        else:
            failed += 1
    return {"attempted": len(ids), "sent": sent, "failed": failed}
