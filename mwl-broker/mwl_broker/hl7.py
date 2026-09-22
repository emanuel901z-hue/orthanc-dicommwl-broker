"""Minimal HL7 v2 reader for worklist orders (`ORM^O01`, `OMG^O19`).

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

**Which messages are orders is checked explicitly** (`is_order_message`): the
parser reads ORC/OBR/PID, and an `ORU^R01` — a *result* message — carries OBR
segments too. Without the check a RIS that broadcasts reports would quietly fill
the worklist.
"""
import logging
from datetime import datetime

log = logging.getLogger("mwl_broker.hl7")

CANCEL_CODES = {"CA", "OC"}
CHANGE_CODES = {"XO", "SC", "SN", "RE"}
NEW_CODES = {"NW", "NA", "OR"}

# The order messages this broker applies. `ORM^O01` is the classic radiology
# order, `OMG^O19` the general clinical order — same ORC/OBR layout, so the same
# code path; both are named in the IHE statement and the conformance statement.
ORDER_MESSAGE_TYPES = ("ORM^O01", "OMG^O19")
# The matching *responses* come from the filler and are not orders.
ORDER_RESPONSE_TYPES = ("ORM^O02", "OMG^O20")


def message_code(message_type: str) -> str:
    """MSH-9 reduced to `code^trigger`.

    Real messages carry a third component — the message structure
    (`OMG^O19^OMG_O19`, `ORM^O01^ORM_O01`) — and dcm4che's sample set does it for
    every message. Comparing the whole string rejected valid orders.
    """
    parts = (message_type or "").strip().upper().split("^")
    return "^".join(parts[:2])


def is_order_message(message_type: str) -> bool:
    """Is this message type an order the broker may turn into a worklist entry?"""
    return message_code(message_type) in ORDER_MESSAGE_TYPES


def describe_message_type(message_type: str) -> str:
    """Why a message is not applied — one plain sentence, or `''` when it is.

    The wording matters: the operator sees this in the HL7 panel and in the
    ACK/error text, and "not an order" is the difference between a report that
    was ignored and a worklist entry that should not exist.
    """
    message = message_code(message_type)
    if message in ORDER_MESSAGE_TYPES:
        return ""
    if message in ORDER_RESPONSE_TYPES:
        return f"{message} is an order response (from the filler), not an order"
    if message.startswith("ADT^"):
        return (f"{message} is a patient event — it belongs on the ADT path "
                "(POST /api/v1/hl7/adt)")
    if message.startswith("ORU^"):
        return (f"{message} is a result/report message, not an order — it must "
                "not create a worklist entry")
    return (f"{message or 'unknown'} is not an order message (accepted: "
            f"{', '.join(ORDER_MESSAGE_TYPES)})")


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
        # is this message an order at all? A report (ORU) has OBR segments too,
        # so the answer cannot be "it parsed fine"
        "supported": is_order_message(message_type),
        "reject_reason": describe_message_type(message_type),
        "warnings": warnings,
    }


def is_cancel(parsed: dict) -> bool:
    return parsed.get("order_control", "").upper() in CANCEL_CODES


def build_ack(control_id: str, ok: bool = True, error: str = "",
              incoming: str = "", receiving_facility: str = "") -> str:
    """MLLP acknowledgement (MSA) for a received message.

    An ACK **swaps** the addressing fields (HL7 v2, chapter 2): what was the
    sender becomes the receiver. The previous version left MSH-4..6 empty, which
    shifted everything: the timestamp landed in MSH-6, "ACK" in MSH-8 and the
    control ID in MSH-9 — a strict engine reads that as "no acknowledgement for
    my message" and keeps resending. Found by a foreign HL7 stack (dcm4che).
    """
    code = "AA" if ok else "AE"
    text = error.replace("|", "/")[:200] if error else ""
    msh = _segments(incoming)[0] if incoming else []
    # the incoming sender becomes our receiver (MSH-3/4 → MSH-5/6)
    their_app = _field(msh, 3, msh=True) or "RIS"
    # never empty: a strict engine rejects an ACK without MSH-6
    their_facility = _field(msh, 4, msh=True) or receiving_facility or "RIS"
    our_facility = _field(msh, 6, msh=True) or "MWLBROKER"
    return (
        f"MSH|^~\\&|MWLBROKER|{our_facility}|{their_app}|{their_facility}|"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}||ACK|{control_id}|P|2.5\r"
        f"MSA|{code}|{control_id}|{text}\r"
    )


def now_hl7() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def peek_type(text: str) -> str:
    """MSH-9 of a message without parsing the rest — MLLP needs to route by it."""
    for segment in _segments(text):
        if segment and segment[0].upper() == "MSH":
            return _field(segment, 9, msh=True)
    return ""


def parse_adt(text: str) -> dict:
    """Parse an ADT message — what patient-identifier and demographic events need.

    | Event | Meaning                              | Segments used |
    |-------|--------------------------------------|---------------|
    | `A08` | patient information update            | PID-3, PID-5, PID-7, PID-8 |
    | `A24` | link two patient records (both stay)  | MRG-1, PID-3 |
    | `A40` | merge (the old identifier is retired) | MRG-1, PID-3 |
    | `A47` | unlink                                | MRG-1, PID-3 |

    Every other ADT event is recognised and reported but not acted upon.
    """
    segments = _segments(text)
    by_name: dict[str, list[list[str]]] = {}
    for segment in segments:
        by_name.setdefault(segment[0].upper(), []).append(segment)

    warnings: list[str] = []
    msh = by_name.get("MSH", [[]])[0]
    pid = by_name.get("PID", [[]])[0]
    mrg = by_name.get("MRG", [[]])[0]

    message_type = _field(msh, 9, msh=True)
    control_id = _field(msh, 10, msh=True)
    if not control_id:
        warnings.append("MSH-10 (message control ID) is missing")

    event = message_type.split("^")[1] if "^" in message_type else ""
    # PID-3 is "id^^^authority^type"; the id is the first component
    new_patient_id = _component(_field(pid, 3), 0)
    old_patient_id = _component(_field(mrg, 1), 0)
    # PID-5 is "Last^First^Middle^Suffix^Prefix" — the same component order the
    # modality shows, so it passes through unchanged (trailing empty components
    # included, exactly like the ORM path above)
    patient_name = _field(pid, 5)
    birth_date = _format_date(_field(pid, 7))
    sex = _field(pid, 8).strip()[:4]

    if event in ("A24", "A40", "A47"):
        if not old_patient_id:
            warnings.append(f"{event} without MRG-1 (the previous patient ID)")
        if event != "A47" and not new_patient_id:
            warnings.append(f"{event} without PID-3 (the surviving patient ID)")
    elif event == "A08":
        if not new_patient_id:
            warnings.append("A08 without PID-3 (the patient ID)")
        if not (patient_name or birth_date or sex):
            warnings.append("A08 carries no PID-5/PID-7/PID-8 to update")

    return {
        "message_type": message_type or "ADT^A40",
        "event": event,
        "control_id": control_id,
        "old_patient_id": old_patient_id,
        "new_patient_id": new_patient_id,
        "patient_name": patient_name,
        "birth_date": birth_date,
        "sex": sex,
        "warnings": warnings,
    }
