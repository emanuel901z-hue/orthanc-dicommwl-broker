"""IHE ATNA audit trail — DICOM PS3.15 audit messages over syslog.

The hospital runs its own Audit Record Repository, so the broker only has to
*produce* correct messages and ship them: RFC 3881 / DICOM PS3.15 XML inside an
RFC 5424 syslog message, over plain TCP or TLS.

Like alerting, this must never touch the DICOM path: messages go into a bounded
queue and a worker thread drains it. If the ARR is unreachable the queue fills
up and the oldest messages are dropped (counted) — an audit endpoint that is
down must not stall a modality.

PHI: an audit trail exists to record *who accessed which patient*, so the patient
ID is part of the message (that is the point). The patient *name* is not, and the
broker's own logs stay PHI-free as before.
"""
import logging
import queue
import socket
import ssl
import threading
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from . import metrics, settings_service

log = logging.getLogger("mwl_broker.atna")

# DICOM coded values (PS3.16)
EVENT_QUERY = ("110112", "Query")
EVENT_IMPORT = ("110104", "Import")
EVENT_EXPORT = ("110106", "Export")
EVENT_SECURITY = ("110113", "Security Alert")

SOURCE_ROLE = ("110153", "Source Role ID")
DESTINATION_ROLE = ("110152", "Destination Role ID")

# one audit message per syslog line; bounded so a dead ARR cannot eat memory
_queue: "queue.Queue[bytes]" = queue.Queue(maxsize=10000)
_worker: threading.Thread | None = None
_stop = threading.Event()
_lock = threading.Lock()


# ── settings ───────────────────────────────────────────────────────────


# The DICOM path asks "is auditing configured?" for every query and instance —
# a short TTL keeps that off the database without making the UI wait long.
_config_cache: dict = {"at": 0.0, "value": None}
_CONFIG_TTL_S = 2.0


def _config() -> dict:
    import time

    now = time.monotonic()
    cached = _config_cache["value"]
    if cached is not None and (now - _config_cache["at"]) < _CONFIG_TTL_S:
        return cached
    value = {
        "enabled": settings_service.get_bool("atna_enabled"),
        "host": settings_service.get_str("atna_syslog_host").strip(),
        "port": settings_service.get_int("atna_syslog_port"),
        "protocol": (settings_service.get_str("atna_syslog_protocol") or "tcp").strip().lower(),
        "ca_file": settings_service.get_str("atna_tls_ca_file").strip(),
        "queue_max": settings_service.get_int("atna_queue_max"),
    }
    _config_cache["at"] = now
    _config_cache["value"] = value
    return value


def enabled() -> bool:
    return bool(_config()["enabled"])


def host() -> str:
    return str(_config()["host"])


def port() -> int:
    return int(_config()["port"])


def protocol() -> str:
    return str(_config()["protocol"])


def ca_file() -> str:
    return str(_config()["ca_file"])


def queue_max() -> int:
    return int(_config()["queue_max"])


def configured() -> bool:
    return enabled() and bool(host())


# ── message building ───────────────────────────────────────────────────


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _participant(role: tuple[str, str], user_id: str, is_requestor: bool,
                 network_id: str = "", network_type: str = "2") -> str:
    code, text = role
    return (
        f'<ActiveParticipant UserID="{escape(user_id)}" '
        f'UserIsRequestor="{"true" if is_requestor else "false"}"'
        + (f' NetworkAccessPointID="{escape(network_id)}" '
           f'NetworkAccessPointTypeCode="{network_type}"' if network_id else "")
        + ">"
        f'<RoleIDCode csd-code="{code}" codeSystemName="DCM" originalText="{text}"/>'
        "</ActiveParticipant>"
    )


def _object(participant_id: str, type_code: str, type_role: str,
            id_code: str, id_system: str, id_text: str, name: str = "") -> str:
    return (
        f'<ParticipantObjectIdentification ParticipantObjectID="{escape(participant_id)}" '
        f'ParticipantObjectTypeCode="{type_code}" '
        f'ParticipantObjectTypeCodeRole="{type_role}">'
        f'<ParticipantObjectIDTypeCode csd-code="{id_code}" '
        f'codeSystemName="{id_system}" originalText="{id_text}"/>'
        + (f"<ParticipantObjectName>{escape(name)}</ParticipantObjectName>" if name else "")
        + "</ParticipantObjectIdentification>"
    )


def build(event: tuple[str, str], *, action: str = "E", outcome: str = "0",
          broker_aet: str = "", source_aet: str = "", destination_aet: str = "",
          source_ip: str = "",
          patient_id: str = "", study_uid: str = "", accession: str = "",
          event_type: tuple[str, str] | None = None, query: str = "",
          timestamp: datetime | None = None) -> str:
    """Build one ATNA audit message (XML string, no syslog framing)."""
    code, text = event
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<AuditMessage xmlns="http://www.w3.org/2001/XMLSchema-instance"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xmlns:xs="http://www.w3.org/2001/XMLSchema">',
        f'<EventIdentification EventActionCode="{action}" '
        f'EventDateTime="{_iso(timestamp)}" EventOutcomeIndicator="{outcome}">',
        f'<EventID csd-code="{code}" codeSystemName="DCM" originalText="{text}"/>',
    ]
    if event_type is not None:
        type_code, type_text = event_type
        parts.append(f'<EventTypeCode csd-code="{type_code}" '
                     f'codeSystemName="IHE Transactions" originalText="{type_text}"/>')
    parts.append("</EventIdentification>")

    if source_aet:
        parts.append(_participant(SOURCE_ROLE, source_aet, True, source_ip))
    parts.append(_participant(DESTINATION_ROLE,
                              destination_aet or broker_aet or "MWLBROKER", False))
    parts.append('<AuditSourceIdentification AuditSourceID="MWLBROKER">'
                 f'<AuditSourceTypeCode csd-code="4" codeSystemName="DCM" '
                 'originalText="Application Server Process"/></AuditSourceIdentification>')

    if patient_id:
        parts.append(_object(patient_id, "1", "1", "2", "RFC-3881", "Patient Number"))
    if study_uid:
        parts.append(_object(study_uid, "2", "3", "110180", "DCM", "Study Instance UID"))
    if accession:
        parts.append(_object(accession, "2", "4", "110181", "DCM", "Accession Number"))
    if query:
        parts.append(_object(query, "2", "24", "110182", "DCM", "Worklist Query",
                             name=escape(query)))
    parts.append("</AuditMessage>")
    return "".join(parts)


def syslog_message(xml: str, timestamp: datetime | None = None) -> bytes:
    """Wrap an audit message in an RFC 5424 syslog frame (DICOM requires the BOM)."""
    facility, severity = 10, 6  # security/authorization, informational
    pri = facility * 8 + severity
    header = (
        f"<{pri}>1 {_iso(timestamp)} {socket.gethostname()} mwl-broker - - - "
    ).encode("utf-8")
    return header + b"\xef\xbb\xbf" + xml.encode("utf-8")


# ── transport ──────────────────────────────────────────────────────────


def _connect(timeout_s: int = 5):
    target = (host(), port())
    if protocol() == "tls":
        context = ssl.create_default_context(cafile=ca_file() or None)
        return context.wrap_socket(socket.create_connection(target, timeout_s),
                                   server_hostname=host())
    return socket.create_connection(target, timeout_s)


def deliver(frame: bytes) -> tuple[bool, str]:
    """Send one frame to the audit repository. Returns (ok, error)."""
    if not host():
        return False, "no audit repository configured"
    try:
        with _connect() as sock:
            sock.sendall(frame)
        return True, ""
    except Exception as exc:
        return False, str(exc)[:200]


def _worker_loop() -> None:
    while not _stop.is_set():
        try:
            frame = _queue.get(timeout=0.5)
        except queue.Empty:
            continue
        ok, error = deliver(frame)
        if ok:
            metrics.ATNA_SENT.labels(event="audit").inc()
        else:
            metrics.ATNA_FAILED.labels(event="audit").inc()
            log.warning("atna: delivery failed: %s", error)
        metrics.ATNA_QUEUE.set(_queue.qsize())


def start() -> None:
    """Start the drain worker (idempotent)."""
    global _worker
    with _lock:
        if _worker is not None and _worker.is_alive():
            return
        _stop.clear()
        _worker = threading.Thread(target=_worker_loop, daemon=True)
        _worker.start()


def stop() -> None:
    _stop.set()
    if _worker is not None:
        _worker.join(timeout=2)


def send(xml: str) -> bool:
    """Queue one audit message (never blocks the DICOM path)."""
    if not configured():
        return False
    frame = syslog_message(xml)
    try:
        _queue.put_nowait(frame)
        metrics.ATNA_QUEUE.set(_queue.qsize())
        return True
    except queue.Full:
        metrics.ATNA_DROPPED.inc()
        log.error("atna: queue full (%d) — dropping an audit message", queue_max())
        return False


def audit(event: tuple[str, str], **kwargs) -> bool:
    """Build and queue one audit message."""
    return send(build(event, **kwargs))


def stats() -> dict:
    return {
        "enabled": enabled(),
        "configured": configured(),
        "host": host(),
        "port": port(),
        "protocol": protocol(),
        "queue_size": _queue.qsize(),
        "queue_max": queue_max(),
        "worker_running": bool(_worker is not None and _worker.is_alive()),
    }


def send_test() -> dict:
    """Send a test audit message synchronously (the UI shows the result)."""
    xml = build(EVENT_SECURITY, outcome="0", broker_aet="MWLBROKER",
                query="MWLBROKER-ATNA-TEST",
                event_type=("ITI-19", "Node Authentication"))
    if not configured():
        return {"ok": False, "error": "audit repository not configured or disabled"}
    ok, error = deliver(syslog_message(xml))
    if ok:
        metrics.ATNA_SENT.labels(event="test").inc()
    else:
        metrics.ATNA_FAILED.labels(event="test").inc()
    log.info("atna: test message to %s:%s (%s) -> %s", host(), port(), protocol(),
             "ok" if ok else error)
    return {"ok": ok, "error": error}


def sample_message() -> str:
    """A complete example message — the ARR team wants to see the format."""
    return build(
        EVENT_QUERY, action="E", outcome="0", broker_aet="MWLBROKER",
        source_aet="CT_01", source_ip="10.0.2.10", destination_aet="MWLBROKER",
        patient_id="P1001", study_uid="1.2.840.113619.2.55.3.1", accession="ACC-A-001",
        query="(0008,0060)=CT", event_type=("ITI-20", "Modality Worklist Query"),
    )


def reset_for_tests() -> None:
    """Drain the queue and the config cache between tests."""
    _config_cache["at"] = 0.0
    _config_cache["value"] = None
    while True:
        try:
            _queue.get_nowait()
        except queue.Empty:
            break
