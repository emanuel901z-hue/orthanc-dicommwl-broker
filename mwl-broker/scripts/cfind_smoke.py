#!/usr/bin/env python3
"""C-FIND smoke test against the broker.

Usage: python scripts/cfind_smoke.py [host] [port] [aet] [--tls] [--ca FILE]
Sends an empty-ish MWL query (all scheduled items for a station) and prints
each answer's key fields. `--tls` connects to the broker's DICOM TLS listener;
`--ca` verifies the server certificate against that bundle (without it the
certificate is accepted without verification, which is enough for a smoke test).
"""
import argparse
import ssl
import sys

from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind

parser = argparse.ArgumentParser(description="C-FIND smoke test against the broker")
parser.add_argument("host", nargs="?", default="127.0.0.1")
parser.add_argument("port", nargs="?", type=int, default=11113)
parser.add_argument("aet", nargs="?", default="MWLBROKER")
parser.add_argument("--tls", action="store_true",
                    help="connect with DICOM TLS (the broker's TLS listener)")
parser.add_argument("--ca", default="", help="CA bundle to verify the server certificate")
args = parser.parse_args()

host, port, aet = args.host, args.port, args.aet

tls_args = None
if args.tls:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if args.ca:
        context.load_verify_locations(cafile=args.ca)
        context.check_hostname = True
    else:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    tls_args = (context, host)

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

assoc = ae.associate(host, port, ae_title=aet, tls_args=tls_args)
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
