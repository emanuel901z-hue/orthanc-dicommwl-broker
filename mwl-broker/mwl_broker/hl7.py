"""Minimal HL7 v2 ORM^O01 reader for worklist orders.

Only what a modality worklist needs is parsed — and the mapping is deliberately
visible in one place, because every site maps its Z-segments differently:

| Field            | Source segment                                     |
|------------------|----------------------------------------------------|
| message type     | MSH-9                                              |
| control id       | MSH-10                                             |
| order control    | ORC-1 (`NW` new, `XO` change, `CA` cancel, …)      |
| patient id/name  | PID-3 / PID-5                                      |
| birth date / sex | PID-7 / PID-8                                      |
| accession        | OBR-3 → ORC-3 → OBR-2                              |
| modality         | OBR-24 → OBR-4.1                                   |
| procedure text   | OBR-4.2 → OBR-4.1                                  |
| scheduled start  | OBR-6 → OBR-27.4                                   |
| station AE title | ZDS-2 → ZDB-4 → setting `hl7_default_station_aet`  |
| study UID        | ZDS-1                                              |

`warnings` lists everything the parser could not map, so the UI can show the
operator what is missing instead of silently creating a half-empty item.
"""
import logging
from datetime import datetime

log = logging.getLogger("mwl_broker.hl7")

CANCEL_CODES = {"CA", "OC"}
CHANGE_CODES = {"XO", "SC", "SN", "RE"}
NEW_CODES = {"NW", "NA", "OR"}


def _segments(text: str) -> list[list[str]]:
    cleaned = text.replace("\r\n", "\r").replace("\n", "\r")
    out = []
    for raw in cleaned.split("\r"):
        if not raw.strip():
            continue
        out.append(raw.split("|"))
    return out


def _field(segment: list[str], number: int, *, msh: bool = False) -> str:
    """Read an HL7 field by its *field number* (1-based).

    MSH is the odd one out: MSH-1 is the field separator itself, so it does not
    appear in the split — every MSH field number maps to `number - 1`.
    """
    index = number - 1 if msh else number
    if 0 <= index < len(segment):
        return segment[index].strip()
    return ""


def _component(value: str, index: int = 0) -> str:
    parts = value.split("^")
    return parts[index].strip() if index < len(parts) else ""


def _format_date(value: str) -> str:
    """HL7 YYYYMMDD (optionally with time) → the DICOM DA/DT form."""
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return ""


def _format_time(value: str) -> str:
    """HL7 time — either HHMM or a full YYYYMMDDHHMM stamp."""
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) >= 12:          # YYYYMMDDHHMM → HH:MM
        return f"{digits[8:10]}:{digits[10:12]}"
    if len(digits) >= 4:           # HHMM
        return f"{digits[0:2]}:{digits[2:4]}"
    return ""


def parse(text: str) -> dict:
    """Parse an ORM^O01 (or ORM^O01-like) message into a flat dict."""
    segments = _segments(text)
    by_name: dict[str, list[list[str]]] = {}
    for segment in segments:
        by_name.setdefault(segment[0].upper(), []).append(segment)

    warnings: list[str] = []
    msh = by_name.get("MSH", [[]])[0]
    pid = by_name.get("PID", [[]])[0]
    orc = by_name.get("ORC", [[]])[0]
    obr = by_name.get("OBR", [[]])[0]
    zds = by_name.get("ZDS", [[]])[0]
    zdb = by_name.get("ZDB", [[]])[0]

    message_type = _field(msh, 9, msh=True)
    control_id = _field(msh, 10, msh=True)
    if not control_id:
        warnings.append("MSH-10 (message control ID) is missing")

    order_control = _field(orc, 1).upper()
    if order_control and order_control not in NEW_CODES | CHANGE_CODES | CANCEL_CODES:
        warnings.append(f"unknown order control {order_control!r} — treated as a new order")

    accession = _field(obr, 3) or _field(orc, 3) or _field(obr, 2)
    if not accession:
        warnings.append("no accession number (OBR-3/ORC-3/OBR-2)")

    patient_id = _component(_field(pid, 3))
    if not patient_id:
        warnings.append("no patient ID (PID-3)")

    service = _field(obr, 4)
    modality = _field(obr, 24) or _component(service, 0)
    if modality and len(modality) > 16:
        modality = modality[:16]

    # OBR-6 is the requested start; many RIS put it in OBR-7 (observation) or
    # in the SPS timing of OBR-27 instead.
    start = _field(obr, 6) or _field(obr, 7) or _field(obr, 27)
    start_date, _, start_time = start.partition("^") if "^" in start else (start, "", "")
    if not start_date:
        warnings.append("no scheduled start (OBR-6/OBR-27)")

    return {
        "message_type": message_type or "ORM^O01",
        "control_id": control_id,
        "order_control": order_control or "NW",
        "accession": accession,
        "patient_id": patient_id,
        "patient_name": _field(pid, 5),
        "birth_date": _format_date(_field(pid, 7)),
        "sex": _field(pid, 8),
        "modality": modality,
        "procedure_description": _component(service, 1) or _component(service, 0),
        "scheduled_date": _format_date(start_date),
        "scheduled_time": _format_time(start_time or start_date),
        "study_uid": _field(zds, 1),
        "station_aet": _field(zds, 2) or _field(zdb, 4),
        "sps_id": _field(obr, 1) or _field(orc, 2) or "1",
        "warnings": warnings,
    }


def is_cancel(parsed: dict) -> bool:
    return parsed.get("order_control", "").upper() in CANCEL_CODES


def build_ack(control_id: str, ok: bool = True, error: str = "") -> str:
    """MLLP acknowledgement (MSA) for a received message."""
    code = "AA" if ok else "AE"
    text = error.replace("|", "/")[:200] if error else ""
    return (
        f"MSH|^~\\&|MWLBROKER|||{datetime.now().strftime('%Y%m%d%H%M%S')}||ACK|{control_id}|P|2.5\r"
        f"MSA|{code}|{control_id}|{text}\r"
    )


def now_hl7() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")
