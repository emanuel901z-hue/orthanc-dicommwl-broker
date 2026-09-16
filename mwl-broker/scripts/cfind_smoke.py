#!/usr/bin/env python3
"""C-FIND smoke test against the broker.

Usage: python scripts/cfind_smoke.py [host] [port] [aet]
Sends an empty-ish MWL query (all scheduled items for a station) and prints
each answer's key fields.
"""
import sys

from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 11113
aet = sys.argv[3] if len(sys.argv) > 3 else "MWLBROKER"

query = Dataset()
query.SpecificCharacterSet = "ISO_IR 100"
query.ScheduledProcedureStepSequence = [Dataset()]
query.ScheduledProcedureStepSequence[0].ScheduledStationAETitle = ""
query.ScheduledProcedureStepSequence[0].ScheduledProcedureStepStartDate = ""
query.ScheduledProcedureStepSequence[0].Modality = ""
query.PatientName = ""
query.PatientID = ""
query.AccessionNumber = ""

ae = AE(ae_title="SMOKETEST")
ae.add_requested_context(ModalityWorklistInformationFind)

assoc = ae.associate(host, port, ae_title=aet)
if not assoc.is_established:
    print(f"FAIL: association to {aet}@{host}:{port} rejected")
    sys.exit(1)

n = 0
for status, ds in assoc.send_c_find(query, ModalityWorklistInformationFind):
    if status is None:
        continue
    if status.Status in (0xFF00, 0xFF01) and ds is not None:
        n += 1
        sps = (ds.get("ScheduledProcedureStepSequence") or [Dataset()])[0]
        print(
            f"  [{n}] acc={ds.get('AccessionNumber')} "
            f"pat={ds.get('PatientName')} "
            f"mod={sps.get('Modality')} "
            f"station={sps.get('ScheduledStationAETitle')} "
            f"date={sps.get('ScheduledProcedureStepStartDate')}"
        )
    elif status.Status == 0x0000:
        print(f"OK: C-FIND finished, {n} answer(s)")
    else:
        print(f"FAIL: status 0x{status.Status:04x}")
        sys.exit(1)

assoc.release()
sys.exit(0 if n else 1)
