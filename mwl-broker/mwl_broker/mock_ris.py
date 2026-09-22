"""Mock MWL SCP for development — simulates a RIS/KIS worklist source.

Run:  python -m mwl_broker.mock_ris --aet RIS_A --port 11114 --variant a

Serves a small set of canned Scheduled Procedure Steps. Matching is a
deliberately simple subset of MWL keys (PatientID, AccessionNumber,
ScheduledStationAETitle, Modality, start date).
"""
import argparse
import fnmatch
import logging
import sys
from datetime import datetime, timedelta

from pydicom.dataset import Dataset
from pydicom.uid import generate_uid
from pynetdicom import AE, evt
from pynetdicom.sop_class import ModalityWorklistInformationFind

log = logging.getLogger("mock_ris")


def _item(patient_id, name, accession, modality, station, desc, day_offset=0):
    sps = Dataset()
    sps.Modality = modality
    sps.ScheduledStationAETitle = station
    dt = datetime.now() + timedelta(days=day_offset)
    sps.ScheduledProcedureStepStartDate = dt.strftime("%Y%m%d")
    sps.ScheduledProcedureStepStartTime = "090000"
    sps.ScheduledProcedureStepID = f"SPS-{accession}"
    sps.ScheduledProcedureStepDescription = desc
    sps.ScheduledPerformingPhysicianName = "House^Doctor"

    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.AccessionNumber = accession
    ds.PatientID = patient_id
    ds.PatientName = name
    ds.PatientBirthDate = "19700101"
    ds.PatientSex = "O"
    ds.StudyInstanceUID = generate_uid()
    ds.RequestedProcedureID = f"RP-{accession}"
    ds.RequestedProcedureDescription = desc
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


VARIANTS = {
    "a": [
        _item("P1001", "Mueller^Hans", "ACC-A-001", "CT", "CT_01", "CT Thorax"),
        _item("P1002", "Schmidt^Anna", "ACC-A-002", "MR", "MR_01", "MR Kopf"),
    ],
    "b": [
        _item("P2001", "Weber^Karl", "ACC-B-001", "DX", "XR_01", "Thorax p.a."),
        _item("P1001", "Mueller^Hans", "ACC-A-001", "CT", "CT_01", "CT Thorax (dupe)"),
    ],
}


def _matches(query: Dataset, item: Dataset) -> bool:
    for tag, attr in (("PatientID", "PatientID"), ("AccessionNumber", "AccessionNumber")):
        want = str(query.get(tag, "") or "")
        if want and not fnmatch.fnmatch(str(item.get(attr, "")), want):
            return False
    q_sps = (query.get("ScheduledProcedureStepSequence") or [Dataset()])[0]
    i_sps = (item.get("ScheduledProcedureStepSequence") or [Dataset()])[0]
    for tag in ("Modality", "ScheduledStationAETitle", "ScheduledProcedureStepStartDate"):
        want = str(q_sps.get(tag, "") or "")
        if want and not fnmatch.fnmatch(str(i_sps.get(tag, "")), want):
            return False
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--aet", default="RIS_A")
    p.add_argument("--port", type=int, default=11114)
    p.add_argument("--variant", default="a", choices=sorted(VARIANTS))
    p.add_argument("--max-associations", type=int, default=20,
                   help="Concurrent associations this mock accepts. pynetdicom's "
                        "default is 1, which makes the mock the bottleneck in any "
                        "load test (and rejects a broker's parallel fan-out) — "
                        "raise it to match a real RIS.")
    args = p.parse_args()

    items = VARIANTS[args.variant]

    def handle_find(event):
        for item in items:
            if _matches(event.identifier, item):
                yield 0xFF00, item
        yield 0x0000, None

    ae = AE(ae_title=args.aet)
    ae.maximum_associations = args.max_associations
    ae.add_supported_context(ModalityWorklistInformationFind)
    from pynetdicom.sop_class import Verification

    ae.add_supported_context(Verification)
    ae.start_server(("0.0.0.0", args.port),
                    block=True, evt_handlers=[(evt.EVT_C_FIND, handle_find)])
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
