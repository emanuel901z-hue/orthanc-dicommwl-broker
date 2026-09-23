#!/usr/bin/env python3
r"""Generate a DVTk C-FIND script from a *real* answer of the running broker.

DVTk's script mode compares the received response against the values declared in
the script. Our worklist answer contains values only the running stack knows
(the mock RIS generates its Study Instance UIDs at start-up, and the scheduled
date is "today + offset"), so a hand-written script can never match. This tool
asks the broker (a real C-FIND) and writes the script with exactly those values.

    python3 generate_mwl_script.py --host 127.0.0.1 --port 11113 --aet MWLBROKER \
        > mwl_live.ds

Then run it with DVTk on the Windows machine:

    DVTCmd.exe "<Query_SCU.ses>" "<path>\mwl_live.ds"

The answer's attribute set is fixed (see `docs/interop.md`), so the generated
script declares exactly what the broker sends — including the nested Scheduled
Procedure Step Sequence.
"""
import argparse

from pydantic import BaseModel
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind

# (tag, VR, path) — top level, then the Scheduled Procedure Step Sequence
TOP_LEVEL = [
    ("0008,0005", "CS", "SpecificCharacterSet"),
    ("0008,0050", "SH", "AccessionNumber"),
    ("0010,0010", "PN", "PatientName"),
    ("0010,0020", "LO", "PatientID"),
    ("0010,0030", "DA", "PatientBirthDate"),
    ("0010,0040", "CS", "PatientSex"),
    ("0020,000D", "UI", "StudyInstanceUID"),
    ("0032,1060", "LO", "RequestedProcedureDescription"),
]
SPS = [
    ("0008,0060", "CS", "Modality"),
    ("0040,0001", "AE", "ScheduledStationAETitle"),
    ("0040,0002", "DA", "ScheduledProcedureStepStartDate"),
    ("0040,0003", "TM", "ScheduledProcedureStepStartTime"),
    ("0040,0006", "PN", "ScheduledPerformingPhysicianName"),
    ("0040,0007", "LO", "ScheduledProcedureStepDescription"),
    ("0040,0009", "SH", "ScheduledProcedureStepID"),
]

# our answer carries the Requested Procedure ID at the *top level*, not inside
# the Scheduled Procedure Step Sequence (DVTk reported it as missing when it was
# declared nested)
EXTRA_TOP_LEVEL = [("0040,1001", "SH", "RequestedProcedureID")]


def _value(dataset, keyword: str) -> str:
    """One DICOM value as text — DICOM padding is not part of the value."""
    value = dataset.get(keyword, "")
    if value is None:
        return ""
    return str(value).strip()


def query(host: str, port: int, aet: str, calling: str) -> list:
    """One real C-FIND against the broker; returns the response datasets."""
    ae = AE(ae_title=calling)
    ae.add_requested_context(ModalityWorklistInformationFind)
    assoc = ae.associate(host, port, ae_title=aet)
    if not assoc.is_established:
        raise SystemExit(f"association to {aet}@{host}:{port} was rejected")

    from pydicom.dataset import Dataset

    identifier = Dataset()
    identifier.QueryRetrieveLevel = "MODALITY WORKLIST"
    identifier.AccessionNumber = ""
    identifier.PatientName = ""
    identifier.ScheduledProcedureStepSequence = [Dataset()]

    answers = []
    try:
        for status, ds in assoc.send_c_find(identifier, ModalityWorklistInformationFind):
            if status and status.Status in (0xFF00, 0xFF01) and ds is not None:
                answers.append(ds)
    finally:
        assoc.release()
    return answers


def render(answers: list) -> str:
    lines = [
        "## Von `generate_mwl_script.py` erzeugt — NICHT von Hand pflegen.",
        "## Die Werte stammen aus einer echten C-FIND-Antwort des laufenden",
        "## Brokers (der Mock-RIS erzeugt seine UIDs beim Start, das Datum ist",
        "## 'heute + Versatz'). Nach einem Neustart des Stacks neu erzeugen.",
        "",
        "SEND ASSOCIATE-RQ (",
        "PRESENTATION-CONTEXT-ITEMS",
        '("Modality Worklist Information Model - FIND SOP Class", "Implicit VR Little Endian")',
        ")",
        "RECEIVE ASSOCIATE-AC (",
        "PRESENTATION-CONTEXT-ITEMS",
        '("Modality Worklist Information Model - FIND SOP Class", 0, "Implicit VR Little Endian")',
        ")",
        'SEND C-FIND-RQ "Modality Worklist Information Model - FIND SOP Class"(',
        '(0x00000003, "Modality Worklist Information Model - FIND SOP Class")',
        '(0x00080052, CS, "MODALITY WORKLIST")',
        '(0x00080050, SH, "")',
        '(0x00100010, PN, "")',
        '(0x00400100, SQ, "")',
        ")",
    ]
    for answer in answers:
        lines.append('RECEIVE C-FIND-RSP "Modality Worklist Information Model - FIND SOP Class"(')
        lines.append("(0x00000900, 0xFF00)")
        lines.append('(0x00000002, "Modality Worklist Information Model - FIND SOP Class")')
        for tag, vr, keyword in TOP_LEVEL + EXTRA_TOP_LEVEL:
            lines.append(f'(0x{tag.replace(",", "")}, {vr}, "{_value(answer, keyword)}")')
        lines.append("(0x00400100, SQ,")
        sps = (answer.get("ScheduledProcedureStepSequence") or [None])[0]
        for tag, vr, keyword in SPS:
            value = _value(sps, keyword) if sps is not None else ""
            lines.append(f'>(0x{tag.replace(",", "")}, {vr}, "{value}")')
        lines.append(")")
        lines.append(")")
    lines += [
        "RECEIVE C-FIND-RSP(",
        "(0x00000900, 0x0000)",
        ")",
        "SEND RELEASE-RQ",
        "RECEIVE RELEASE-RP",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11113)
    parser.add_argument("--aet", default="MWLBROKER", help="called AE title (the broker)")
    parser.add_argument("--calling", default="DVTK_SCU", help="calling AE title")
    args = parser.parse_args()

    answers = query(args.host, args.port, args.aet, args.calling)
    print(render(answers), end="")


if __name__ == "__main__":
    main()
