"""GDT/BDT intake: worklist orders from a practice system without HL7.

GDT ("Gerätedatentransfer") is the German interface between a practice EDP (PVS)
and a device or the RIS. BDT shares the same record layout. A record is a plain
text file, one field per line:

    <3-digit length><4-digit field number><content>

so `01380006302` is length 013, field 8000 (record type), content `6302` — the
declared length counts the two-character CR+LF terminator, which is why it is
two more than the visible line.

**Which records are orders is decided in one place.** GDT 3.0 uses `6302`
("Neue Untersuchung anfordern") for an order; `6300`/`6301` carry master data
and `6310`/`6311` carry examination results. None of those may become a worklist
entry — the same reasoning as the `ORU^R01` check on the HL7 path, and the
reason is reported in plain words.

**The order fields are partly a local convention.** The patient fields are
stable across the standard (3000 patient number, 3101/3102 name, 3103 birth
date, 3110 sex, 8402 the requested examination), but there is no standard
order-number field — vendors make it configurable (measured: labGate). The
built-in defaults below are therefore overridable per site through the
`gdt_field_map` setting; keys that are not semantic names are treated as DICOM
keywords and end up as extra worklist attributes, exactly like `hl7_field_map`.

PHI: a work item carries patient data (the modality needs it). The intake log
keeps only metadata (record type, sender, accession, action) — never the raw
record, which would be PHI.
"""
import json
import logging
import re
from datetime import datetime

from . import settings_service

log = logging.getLogger("mwl_broker.gdt")

# structural fields (the same in every record)
F_RECORD_TYPE = "8000"
F_LENGTH = "8100"
F_RECEIVER = "8315"
F_SENDER = "8316"
F_VERSION = "9218"

# Record types. `6302` is the order; the others are recognised and refused with
# a reason instead of silently filling the worklist.
ORDER_SATZARTEN = ("6302",)            # "Neue Untersuchung anfordern" (PVS → device)
MASTER_DATA_SATZARTEN = ("6300", "6301")   # Stammdaten anfordern / übermitteln
RESULT_SATZARTEN = ("6310", "6311")        # Untersuchungsdaten / -anzeige

# Built-in field numbers per semantic key. Empty = "no standard field"; the
# operator sets it in `gdt_field_map` (the order number is the common case).
DEFAULT_FIELD_MAP: dict[str, str] = {
    "accession": "",             # Auftragsnummer — no standard field, set per site
    "sps_id": "",
    "patient_id": "3000",
    "patient_name": "3101",      # Nachname
    "patient_first_name": "3102",
    "birth_date": "3103",
    "sex": "3110",
    "modality": "",              # 8402 is a Kennfeld, not a DICOM modality code
    "procedure_description": "8402",   # the requested examination
    "scheduled_date": "6200",
    "scheduled_time": "6201",
    "study_uid": "",
    "station_aet": "",
}
SEMANTIC_KEYS = frozenset(DEFAULT_FIELD_MAP)

_LINE_RE = re.compile(r"^(\d{3})(\d{4})(.*)$")
_SEX_MAP = {"1": "M", "2": "F", "3": "O", "M": "M", "W": "F", "F": "F", "0": ""}


def field_map() -> dict[str, str]:
    """Effective field map: the defaults with the site override merged on top."""
    merged = dict(DEFAULT_FIELD_MAP)
    raw = settings_service.get_str("gdt_field_map").strip()
    if raw:
        try:
            override = json.loads(raw)
        except ValueError:
            log.warning("gdt_field_map is not valid JSON — using the defaults")
            return merged
        if isinstance(override, dict):
            merged.update({str(k): str(v) for k, v in override.items()})
    return merged


def is_order_record(record_type: str) -> bool:
    """Is this record type an order the broker may turn into a worklist entry?"""
    return (record_type or "").strip() in ORDER_SATZARTEN


def describe_record_type(record_type: str) -> str:
    """Why a record is not an order — one plain sentence, or `''` when it is."""
    record_type = (record_type or "").strip()
    if record_type in ORDER_SATZARTEN:
        return ""
    if record_type in MASTER_DATA_SATZARTEN:
        return (f"GDT {record_type} is a master-data record (Stammdaten), not an "
                "order — it must not create a worklist entry")
    if record_type in RESULT_SATZARTEN:
        return (f"GDT {record_type} carries examination data (Befund), not an "
                "order — it must not create a worklist entry")
    return (f"{record_type or 'unknown'} is not an order record (accepted: "
            f"{', '.join(ORDER_SATZARTEN)})")


def _format_date(value: str) -> str:
    """GDT date (TTMMJJJJ) → the DICOM form (YYYY-MM-DD)."""
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 8:
        return ""
    day, month, year = digits[0:2], digits[2:4], digits[4:8]
    if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
        return f"{year}-{month}-{day}"
    # a few systems send ISO order (YYYYMMDD) despite the specification
    y, m, d = digits[0:4], digits[4:6], digits[6:8]
    if 1900 <= int(y) <= 2100 and 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
        return f"{y}-{m}-{d}"
    return ""


def _format_time(value: str) -> str:
    """GDT time (HHMMSS or HHMM) → the DICOM form (HH:MM)."""
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) >= 4:
        return f"{digits[0:2]}:{digits[2:4]}"
    return ""


def _map_sex(value: str) -> str:
    return _SEX_MAP.get((value or "").strip().upper(), "")


def _read_fields(text: str) -> tuple[dict[str, str], list[str]]:
    """Split an XDT record into {field number: content}, first occurrence wins."""
    fields: dict[str, str] = {}
    warnings: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw.strip():
            continue
        match = _LINE_RE.match(raw)
        if match is None:
            warnings.append(f"line without a 3+4 digit field header: {raw[:24]!r}")
            continue
        length, number, content = match.group(1), match.group(2), match.group(3)
        declared = int(length)
        # the declared length counts the CR+LF terminator; tolerate a file that
        # ends without one (or uses LF only) instead of warning on every line
        if declared not in (len(raw), len(raw) + 1, len(raw) + 2):
            warnings.append(
                f"field {number}: declared length {declared}, line has {len(raw)} characters")
        fields.setdefault(number, content)
    return fields, warnings


def _derived_accession(patient_id: str, sender: str, date: str) -> str:
    """An order number the PVS did not send: stable per sender, patient and day."""
    stamp = (date or datetime.now().strftime("%Y%m%d")).replace("-", "")
    return f"GDT-{sender or 'X'}-{patient_id or 'X'}-{stamp}"


def parse(text: str) -> dict:
    """Parse one GDT/BDT record into the flat dict the worklist intake expects."""
    fields, warnings = _read_fields(text)
    fmap = field_map()

    def get(key: str) -> str:
        number = fmap.get(key) or ""
        return fields.get(number, "").strip()

    record_type = fields.get(F_RECORD_TYPE, "").strip()
    patient_id = get("patient_id")
    scheduled_date = _format_date(get("scheduled_date"))

    accession = get("accession")
    if not accession:
        if patient_id:
            accession = _derived_accession(patient_id, fields.get(F_SENDER, "").strip(),
                                           scheduled_date)
            warnings.append("no order-number field configured (gdt_field_map) — "
                            f"derived {accession}")
        else:
            warnings.append("no patient number (3000) and no order number — "
                            "cannot identify the order")

    name = "^".join(part for part in (get("patient_name"),
                                      get("patient_first_name")) if part)

    # any non-semantic key is a DICOM keyword the site wants filled
    mapped: dict[str, str] = {}
    for key, number in fmap.items():
        if key in SEMANTIC_KEYS or not number:
            continue
        value = fields.get(number, "").strip()
        if value:
            mapped[key] = value

    if record_type and not is_order_record(record_type):
        warnings.append(describe_record_type(record_type))

    return {
        "protocol": "gdt",
        "message_type": record_type,        # the log column the UI already shows
        "record_type": record_type,
        "control_id": "",                   # GDT has no message control id
        "order_control": "NW",
        "accession": accession,
        "sps_id": get("sps_id") or "1",
        "patient_id": patient_id,
        "patient_name": name,
        "birth_date": _format_date(get("birth_date")),
        "sex": _map_sex(get("sex")),
        "modality": get("modality"),
        "procedure_description": get("procedure_description"),
        "scheduled_date": scheduled_date,
        "scheduled_time": _format_time(get("scheduled_time")),
        "study_uid": get("study_uid"),
        "station_aet": get("station_aet"),
        "sender_id": fields.get(F_SENDER, "").strip(),
        "receiver_id": fields.get(F_RECEIVER, "").strip(),
        "version": fields.get(F_VERSION, "").strip(),
        "mapped": mapped,
        "supported": is_order_record(record_type),
        "reject_reason": describe_record_type(record_type),
        "warnings": warnings,
    }
